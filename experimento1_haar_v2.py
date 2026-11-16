import time
import json
from pathlib import Path
import cv2
import numpy as np
from picarx import Picarx
from vilib import Vilib

# Ajustes del carrito y la deteccion
VELOCIDAD = 15                 # Potencia para avanzar. 
TIEMPO_ALTO = 10.0
TIEMPO_DESPEJADO = 1.5        # Espera despues de que desaparece el peaton.
TIEMPO_ENTRE_ALTOS = 2.0           # Tiempo sin ver la senal para aceptar otro alto.
BRILLO_MINIMO = 35            # Escala de grises: 0 negro, 255 blanco. Esto nos sirve para cuandos se tape la camara repentinamente
TIEMPO_OSCURO = 0.1           # Tiempo con la camara oscura antes de parar.
TIEMPO_SIN_IMAGEN = 1.0

# Posicion de la camara para cada modo. Se ajusta con I, K, J y L.
POSICIONES_CAMARA = {
    1: {"pan": 0, "tilt": 0},     # Alto
    2: {"pan": 0, "tilt": 0},     # Peaton/personaje
}
PASO_CAMARA = 1
LIMITE_CAMARA = 35               # Hasta donde puede girar la camara.
TIEMPO_MOVER_CAMARA = 0.5
ANCHO_MIN_ALTO = 100             # Ancho en pixeles para considerar que el alto esta cerca.
PASO_UMBRAL = 5                  # Cuanto cambia el ancho minimo al presionar + o -.
# Parametros para buscar el alto (1) o el peaton (2).
AJUSTES_DETECCION = {
    1: {"scaleFactor": 1.05, "minNeighbors": 4},
    2: {"scaleFactor": 1.07, "minNeighbors": 4},
}
# Variables que usamos durante la prueba
modo = 0                     # 0 sin seleccionar, 1 alto, 2 peaton.
estado = 'PARO_SEGURO'
motivo = 'Selecciona 1 o 2 y despues W'
contador = 0
alto_habilitado = True
inicio_alto = None
inicio_despejado = None
inicio_oscuro = None
imagen_anterior = None
# monotonic() da segundos de un reloj que no retrocede si cambia la hora del sistema.
# Restamos dos lecturas para saber cuanto tiempo paso. No pausa el programa.
ultima_imagen = time.monotonic()
brillo = 0.0
cajas = []
ventana = 'PiCar-X: 1 Alto / 2 Peaton'
carpeta = Path(__file__).resolve().parent
archivo_ajustes = carpeta / 'ajustes_experimento1.json'
camara_estable_desde = 0.0
ancho_mayor = 0


def cargar_ajustes():
    global ANCHO_MIN_ALTO

    # Si todavia no guardamos ajustes, usamos los valores iniciales.
    if not archivo_ajustes.exists():
        return

    try:
        with open(archivo_ajustes, 'r', encoding='utf-8') as archivo:
            datos = json.load(archivo)

        # Leer la posicion de la camara para cada modo.
        camara_alto = datos['camara']['1']
        camara_peaton = datos['camara']['2']
        ancho = int(datos['ancho_min_alto'])

        POSICIONES_CAMARA[1] = camara_alto
        POSICIONES_CAMARA[2] = camara_peaton
        ANCHO_MIN_ALTO = ancho

    except (OSError, ValueError, KeyError, TypeError):
        print('No se pudieron cargar los ajustes.')


def guardar_ajustes():
    datos = {'camara': POSICIONES_CAMARA, 'ancho_min_alto': ANCHO_MIN_ALTO}
    temporal = archivo_ajustes.with_suffix('.tmp')
    temporal.write_text(json.dumps(datos, indent=2), encoding='utf-8')
    temporal.replace(archivo_ajustes)


def ajustes_camara():
    global camara_estable_desde, inicio_despejado

    px.stop()

    giro = POSICIONES_CAMARA[modo]['pan']
    inclinacion = POSICIONES_CAMARA[modo]['tilt']

    px.set_cam_pan_angle(giro)
    px.set_cam_tilt_angle(inclinacion)

    # Dar tiempo a que se mueva la camara antes de detectar.
    camara_estable_desde = time.monotonic() + TIEMPO_MOVER_CAMARA

    # Reiniciar la espera porque cambiamos la vista de la camara.
    inicio_despejado = None


cargar_ajustes()
px = Picarx()

try:
    px.stop()
    px.set_dir_servo_angle(0)  # Dejar las ruedas derechas.

    alto = cv2.CascadeClassifier(str(carpeta / 'stop_signal_v3.xml'))
    peaton = cv2.CascadeClassifier(str(carpeta / 'character.xml'))
    if alto.empty() or peaton.empty():
        raise RuntimeError('Falta un XML o no es valido. Coloca ambos junto al script.')

    Vilib.camera_start()
    # Mostrar la imagen con OpenCV.
    cv2.namedWindow(ventana)
    print('I/K: inclinar camara | J/L: girar camara | +/-: ajustar ancho del alto | S: guardar')

    while True:
        # Actualizamos el tiempo en cada vuelta; ahora - inicio_alto da los segundos del alto.
        ahora = time.monotonic()
        imagen = Vilib.img
        valida = (isinstance(imagen, np.ndarray) and imagen.size > 0
                  and imagen.ndim == 3 and imagen.shape[2] == 3)
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

            # Esperar a que se acomode la camara y revisar si esta tapada.
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

                # Usar el detector del modo seleccionado.
                if modo == 1:
                    cajas = alto.detectMultiScale(gris, **AJUSTES_DETECCION[1])
                elif modo == 2:
                    cajas = peaton.detectMultiScale(gris, **AJUSTES_DETECCION[2])

                detectado = len(cajas) > 0
                ancho_mayor = max((int(w) for x, y, w, h in cajas), default=0)
                # Solo paramos si el alto esta cerca. Para aceptar otro,
                # la senal anterior debe dejar de verse, aunque este lejos.
                # Para el alto revisamos que este cerca; para el peaton basta con verlo.
                if modo == 1:
                    confirmado = ancho_mayor >= ANCHO_MIN_ALTO
                else:
                    confirmado = detectado

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
                        tiempo_espera = TIEMPO_ENTRE_ALTOS if modo == 1 else TIEMPO_DESPEJADO
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
                etiqueta = ('Cerca' if cerca else 'Lejos') if modo == 1 else 'Peaton'
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

        if estado != 'AVANCE':
            px.stop()

        # Mostrar la imagen solo si la camara entrego una captura valida.
        if valida:
            # Dejar en pantalla solo el modo, el estado y el tiempo del alto.
            pantalla = video.copy()
            nombre_modo = {0: 'Sin seleccionar', 1: 'Alto', 2: 'Peaton'}[modo]
            textos = [f'{nombre_modo} | {estado.replace("_", " ")}',
                      '1/2 modo | W avanzar | Espacio/D parar | Q salir']
            if estado == 'ALTO_10S':
                textos.append(f'Faltan {max(0, TIEMPO_ALTO-(ahora-inicio_alto)):.1f} segundos')
            if estado == 'PARO_SEGURO':
                textos.append(motivo)
            for i, texto in enumerate(textos):
                cv2.putText(pantalla, texto, (8, 22 + 25*i),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
                cv2.putText(pantalla, texto, (8, 22 + 25*i),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

            cv2.imshow(ventana, pantalla)

        # Leer las teclas aunque todavia no tengamos imagen.
        tecla = chr(cv2.waitKey(10) & 0xFF).lower()

        # Al cambiar de modo, el carrito se detiene.
        if tecla in ('q', '\x1b'):
            break
        if cv2.getWindowProperty(ventana, cv2.WND_PROP_VISIBLE) < 1:
            break
        if tecla in ('1', '2'):
            modo = int(tecla)
            estado = 'PARO_SEGURO'
            ajustes_camara()
            motivo = 'Modo seleccionado. Espera camara y presiona W'
            alto_habilitado = True
            inicio_alto = None
        elif tecla in ('i', 'k', 'j', 'l') and modo:
            # Terminar la espera o parar con espacio antes de ajustar la camara.
            if estado in ('ALTO_10S', 'ESPERA_PEATON'):
                print('Para ajustar camara, detente primero con ESPACIO')
            else:
                estado = 'PARO_SEGURO'
                eje = 'tilt' if tecla in ('i', 'k') else 'pan'
                cambio = PASO_CAMARA if tecla in ('i', 'j') else -PASO_CAMARA
                POSICIONES_CAMARA[modo][eje] = max(-LIMITE_CAMARA, min(
                    LIMITE_CAMARA, POSICIONES_CAMARA[modo][eje] + cambio))
                ajustes_camara()
                motivo = 'Camara ajustada. W para avanzar'
                #print(f"Camara: giro {POSICIONES_CAMARA[modo]['pan']} | inclinacion {POSICIONES_CAMARA[modo]['tilt']}. S para guardar.")
        elif tecla in ('+', '=', '-') and modo == 1 and valida:
            if estado in ('ALTO_10S', 'ESPERA_PEATON'):
                print('Para ajustar umbral, detente primero con ESPACIO')
            else:
                px.stop()
                estado = 'PARO_SEGURO'
                cambio = -PASO_UMBRAL if tecla == '-' else PASO_UMBRAL
                ANCHO_MIN_ALTO = max(5, min(imagen.shape[1], ANCHO_MIN_ALTO + cambio))
                contador = 0
                inicio_despejado = None
                motivo = 'Umbral ajustado. Presiona W'
                #print(f"Ancho minimo: {ANCHO_MIN_ALTO}px. S para guardar.")
        elif tecla == 's':
            try:
                guardar_ajustes()
                print('Ajustes guardados.')
            except OSError as error:
                print('No se pudieron guardar los ajustes', error)
        elif tecla in (' ', 'd'):
            estado = 'PARO_SEGURO'
            motivo = 'Parada manual. Presiona W para reiniciar'
        elif tecla == 'w':
            # W solo permite salir del paro cuando la camara ya esta lista.
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

        # Avanzar solo en el estado AVANCE.
        if estado == 'AVANCE':
            px.forward(VELOCIDAD)
        else:
            px.stop()

except KeyboardInterrupt:
    print('Programa interrumpido.')
finally:
    # Detener el carrito al salir, incluso si ocurre un error.
    px.stop()
    try:
        Vilib.camera_close()
    finally:
        cv2.destroyAllWindows()