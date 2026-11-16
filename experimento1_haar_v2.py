"""PiCar-X - Experimento 1. Ejecutar este archivo desde el editor de Python.
Poner los dos XML en la misma carpeta que este archivo.
Teclas en la ventana de video: 1 alto, 2 peaton, W avanzar,
ESPACIO o D parar, Q o ESC salir. Al cambiar modo siempre se detiene.
I/K: inclinacion +/-; J/L: giro +/-; S: guardar ajustes.
+/-: umbral del alto (modo 1). Ajustar camara detiene el carrito.
Usa Vilib + OpenCV. Cerrar otros programas que utilicen la camara.
"""
import time
import json
from pathlib import Path

import cv2
import numpy as np
from picarx import Picarx
from vilib import Vilib

# ---------- VALORES QUE PUEDEN AJUSTAR ----------
POTENCIA = 15                 # Potencia de motores, NO velocidad en km/h.
CONFIRMACIONES = 3            # Tres imagenes nuevas seguidas con deteccion.
TIEMPO_ALTO = 10.0
TIEMPO_DESPEJADO = 2.0        # Peaton: esperar sin detecciones antes de avanzar.
TIEMPO_REARME = 2.0           # Alto: desaparecer para habilitar otro alto.
BRILLO_MINIMO = 35            # Escala de grises: 0 negro, 255 blanco.
TIEMPO_OSCURO = 0.1           # Oscuridad sostenida para ordenar paro seguro.
TIEMPO_SIN_IMAGEN = 1.0

# Camara: grados relativos al cero calibrado del PiCar-X.
# Los valores iniciales son neutros: ajustarlos con el carrito detenido.
CAMARA_POR_MODO = {
    1: {"pan": 0, "tilt": 0},     # Alto
    2: {"pan": 0, "tilt": 0},     # Peaton/personaje
}
PASO_CAMARA = 2
LIMITE_CAMARA = 35               # Limite conservador para ambos ejes.
TIEMPO_ASENTAR_CAMARA = 0.5
ANCHO_MIN_ALTO = 100             # EJEMPLO: calibrar; no son centimetros.
PASO_UMBRAL = 5                  # Teclas +/-; pixeles del frame procesado.
HAAR_POR_MODO = {
    1: {"scaleFactor": 1.1, "minNeighbors": 4},
    2: {"scaleFactor": 1.07, "minNeighbors": 4},
}
# Conservar aqui los parametros que funcionaron con CADA modelo.
# ---------- VARIABLES DEL PROGRAMA ----------
modo = 0                     # 0 sin seleccionar, 1 alto, 2 peaton.
estado = 'PARO_SEGURO'
motivo = 'Selecciona 1 o 2 y despues W'
contador = 0
alto_habilitado = True
inicio_alto = None
inicio_despejado = None
inicio_oscuro = None
imagen_anterior = None
ultima_imagen = time.monotonic()
brillo = 0.0
cajas = []
video = np.zeros((480, 640, 3), dtype=np.uint8)
ventana = 'PiCar-X: 1 Alto / 2 Peaton'
carpeta = Path(__file__).resolve().parent
archivo_ajustes = carpeta / 'ajustes_experimento1.json'
camara_estable_desde = 0.0
ancho_mayor = 0
aviso = ''


def cargar_ajustes():
    global ANCHO_MIN_ALTO
    if not archivo_ajustes.exists():
        return
    try:
        datos = json.loads(archivo_ajustes.read_text(encoding='utf-8'))
        nuevas = {}
        for m in (1, 2):
            nuevas[m] = {}
            for eje in ('pan', 'tilt'):
                valor = int(datos['camara'][str(m)][eje])
                nuevas[m][eje] = max(-LIMITE_CAMARA, min(LIMITE_CAMARA, valor))
        umbral = int(datos['ancho_min_alto'])
        if not 5 <= umbral <= 640:
            raise ValueError('Umbral fuera del rango 5..640')
        CAMARA_POR_MODO.update(nuevas)
        ANCHO_MIN_ALTO = umbral
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'No se cargaron ajustes; se usan los iniciales: {error}')


def guardar_ajustes():
    datos = {'camara': CAMARA_POR_MODO, 'ancho_min_alto': ANCHO_MIN_ALTO}
    temporal = archivo_ajustes.with_suffix('.tmp')
    temporal.write_text(json.dumps(datos, indent=2), encoding='utf-8')
    temporal.replace(archivo_ajustes)


def aplicar_camara():
    global camara_estable_desde, contador, inicio_despejado, cajas, ancho_mayor
    px.stop()
    posicion = CAMARA_POR_MODO[modo]
    px.set_cam_pan_angle(posicion['pan'])
    px.set_cam_tilt_angle(posicion['tilt'])
    camara_estable_desde = time.monotonic() + TIEMPO_ASENTAR_CAMARA
    contador = 0
    inicio_despejado = None
    cajas = []
    ancho_mayor = 0


cargar_ajustes()
px = Picarx()

try:
    px.stop()
    px.set_dir_servo_angle(0)  # Trayectoria recta; no es seguimiento de carril.

    alto = cv2.CascadeClassifier(str(carpeta / 'stop_signal_v3.xml'))
    peaton = cv2.CascadeClassifier(str(carpeta / 'character.xml'))
    if alto.empty() or peaton.empty():
        raise RuntimeError('Falta un XML o no es valido. Coloca ambos junto al script.')

    Vilib.camera_start()
    # La ventana la muestra OpenCV; no necesitamos transmision web de Vilib.
    cv2.namedWindow(ventana)

    while True:
        ahora = time.monotonic()
        imagen = Vilib.img
        valida = isinstance(imagen, np.ndarray) and imagen.size > 0 and imagen.ndim == 3
        nueva = valida and imagen is not imagen_anterior

        if nueva:
            # Procesar cada imagen nueva una sola vez.
            imagen_anterior = imagen
            ultima_imagen = ahora
            video = imagen.copy()
            gris = cv2.cvtColor(video, cv2.COLOR_BGR2GRAY)
            brillo = float(np.mean(gris))
            cajas = []
            ancho_mayor = 0

            # 1. Imagen oscura: mide el promedio de intensidad de todos los pixeles.
            if ahora < camara_estable_desde:
                contador = 0
                inicio_despejado = None
                inicio_oscuro = None
            elif brillo < BRILLO_MINIMO:
                if inicio_oscuro is None:
                    inicio_oscuro = ahora
                contador = 0
                inicio_despejado = None
                if ahora - inicio_oscuro >= TIEMPO_OSCURO:
                    estado = 'PARO_SEGURO'
                    motivo = 'Camara oscura/tapada. Destapa y presiona W'
            else:
                inicio_oscuro = None

                # 2. Elegir UNA cascada segun el modo seleccionado.
                if modo == 1:
                    cajas = alto.detectMultiScale(gris, **HAAR_POR_MODO[1])
                elif modo == 2:
                    cajas = peaton.detectMultiScale(gris, **HAAR_POR_MODO[2])

                detectado = len(cajas) > 0
                ancho_mayor = max((int(w) for x, y, w, h in cajas), default=0)
                # Detectar lejos NO activa el alto. Para rearmar usamos detectado,
                # que incluye TODAS las senales, incluso las pequenas.
                candidato = ancho_mayor >= ANCHO_MIN_ALTO if modo == 1 else detectado
                if candidato:
                    contador = min(contador + 1, CONFIRMACIONES)
                else:
                    contador = 0
                confirmado = contador >= CONFIRMACIONES

                # Alto: parar 10 s. Peaton: parar hasta que deje de verse.
                if estado != 'PARO_SEGURO':
                    if modo == 1 and estado == 'ALTO_10S':
                        if ahora - inicio_alto >= TIEMPO_ALTO:
                            estado = 'AVANCE'
                            inicio_despejado = None
                            contador = 0
                    elif ((modo == 1 and not alto_habilitado)
                          or (modo == 2 and estado == 'ESPERA_PEATON')):
                        # Ambos modos esperan un tiempo sin detecciones.
                        tiempo_espera = TIEMPO_REARME if modo == 1 else TIEMPO_DESPEJADO
                        if detectado:
                            inicio_despejado = None
                        elif inicio_despejado is None:
                            inicio_despejado = ahora
                        elif ahora - inicio_despejado >= tiempo_espera:
                            alto_habilitado = True
                            estado = 'AVANCE'
                            inicio_despejado = None
                            contador = 0
                    elif confirmado and estado == 'AVANCE':
                        inicio_despejado = None
                        if modo == 1:
                            estado = 'ALTO_10S'
                            inicio_alto = ahora
                            alto_habilitado = False
                        elif modo == 2:
                            estado = 'ESPERA_PEATON'

            for x, y, w, h in cajas:
                cerca = modo != 1 or w >= ANCHO_MIN_ALTO
                color = (0, 255, 0) if cerca else (0, 255, 255)
                etiqueta = f'Alto {w}px: {"CERCA" if cerca else "LEJOS"}' if modo == 1 else 'Peaton'
                cv2.rectangle(video, (x, y), (x+w, y+h), color, 2)
                cv2.putText(video, etiqueta, (x, max(18, y-6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Parar si la camara deja de entregar imagenes nuevas.
        if not valida or time.monotonic() - ultima_imagen > TIEMPO_SIN_IMAGEN:
            estado = 'PARO_SEGURO'
            motivo = 'Sin imagen nueva de camara'
            contador = 0
            inicio_despejado = None
            inicio_oscuro = None

        # Mostrar estado, deteccion y brillo (para ajustar el umbral al tapar).
        pantalla = video.copy()
        textos = [f'Modo: {modo} | Estado: {estado}',
                  f'Brillo: {brillo:.1f} | Limite oscuro: {BRILLO_MINIMO}',
                  f'Detecciones: {len(cajas)} | Confirmacion: {contador}/{CONFIRMACIONES}',
                  '1 alto | 2 peaton | W avanzar | ESPACIO/D parar | Q salir']
        if modo:
            posicion = CAMARA_POR_MODO[modo]
            textos.append(f"Camara: pan {posicion['pan']} | tilt {posicion['tilt']} grados")
        if modo == 1:
            textos.append(f'Alto ancho: {ancho_mayor}px | Umbral: {ANCHO_MIN_ALTO}px (+/-)')
        textos.append('I/K tilt +/- | J/L pan +/- | S guardar ajustes')
        if aviso:
            textos.append(aviso)
        if estado == 'ALTO_10S':
            textos.append(f'Faltan {max(0, TIEMPO_ALTO-(ahora-inicio_alto)):.1f} segundos')
        if estado == 'PARO_SEGURO':
            textos.append(motivo)
        for i, texto in enumerate(textos):
            cv2.putText(pantalla, texto, (8, 22 + 25*i),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
            cv2.putText(pantalla, texto, (8, 22 + 25*i),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        # Aplicar primero cualquier detencion detectada, antes de mostrar la ventana.
        if estado != 'AVANCE':
            px.stop()
        cv2.imshow(ventana, pantalla)
        tecla = chr(cv2.waitKey(10) & 0xFF).lower()

        # Teclado: cambiar modo SIEMPRE detiene el carrito.
        if tecla in ('q', '\x1b'):
            break
        if cv2.getWindowProperty(ventana, cv2.WND_PROP_VISIBLE) < 1:
            break
        if tecla in ('1', '2'):
            modo = int(tecla)
            estado = 'PARO_SEGURO'
            aplicar_camara()
            motivo = 'Modo seleccionado. Espera camara y presiona W'
            alto_habilitado = True
            inicio_alto = None
        elif tecla in ('i', 'k', 'j', 'l') and modo:
            # Solo se permite calibrar desde paro/avance, nunca saltarse una espera.
            if estado in ('ALTO_10S', 'ESPERA_PEATON'):
                aviso = 'Para ajustar camara, detente primero con ESPACIO'
            else:
                estado = 'PARO_SEGURO'
                eje = 'tilt' if tecla in ('i', 'k') else 'pan'
                cambio = PASO_CAMARA if tecla in ('i', 'j') else -PASO_CAMARA
                CAMARA_POR_MODO[modo][eje] = max(-LIMITE_CAMARA, min(
                    LIMITE_CAMARA, CAMARA_POR_MODO[modo][eje] + cambio))
                aplicar_camara()
                motivo = 'Camara ajustada. Espera y presiona W'
                aviso = 'Ajustes pendientes de guardar: S'
        elif tecla in ('+', '=', '-') and modo == 1:
            if estado in ('ALTO_10S', 'ESPERA_PEATON'):
                aviso = 'Para ajustar umbral, detente primero con ESPACIO'
            else:
                px.stop()
                estado = 'PARO_SEGURO'
                cambio = -PASO_UMBRAL if tecla == '-' else PASO_UMBRAL
                ANCHO_MIN_ALTO = max(5, min(video.shape[1], ANCHO_MIN_ALTO + cambio))
                contador = 0
                inicio_despejado = None
                motivo = 'Umbral ajustado. Presiona W'
                aviso = 'Ajustes pendientes de guardar: S'
        elif tecla == 's':
            try:
                guardar_ajustes()
                aviso = 'Camara de ambos modos y umbral guardados'
            except OSError as error:
                aviso = 'No se pudieron guardar los ajustes (ver consola)'
                print(error)
        elif tecla in (' ', 'd'):
            estado = 'PARO_SEGURO'
            motivo = 'Parada manual. Presiona W para reiniciar'
        elif tecla == 'w':
            # No permitir que W salte el alto ni la espera del peaton.
            if (estado == 'PARO_SEGURO' and modo != 0 and valida
                    and brillo >= BRILLO_MINIMO
                    and ultima_imagen >= camara_estable_desde
                    and time.monotonic() - ultima_imagen <= TIEMPO_SIN_IMAGEN):
                estado = 'AVANCE'
                contador = 0
                alto_habilitado = True
                inicio_alto = None
                inicio_despejado = None
                motivo = ''

        # Un solo lugar ordena avanzar. Todos los demas estados detienen.
        if estado == 'AVANCE':
            px.forward(POTENCIA)
        else:
            px.stop()

except KeyboardInterrupt:
    print('Programa interrumpido.')
finally:
    # Si hay un error, Ctrl+C o salida normal, detener antes de cerrar la camara.
    px.stop()
    try:
        Vilib.camera_close()
    finally:
        cv2.destroyAllWindows()
