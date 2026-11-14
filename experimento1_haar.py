"""PiCar-X - Experimento 1. Ejecutar este archivo desde el editor de Python.
Poner los dos XML en la misma carpeta que este archivo.
Teclas en la ventana de video: 1 alto, 2 peaton, W avanzar,
ESPACIO o D parar, Q o ESC salir. Al cambiar modo siempre se detiene.
Usa Vilib + OpenCV. Cerrar otros programas que utilicen la camara.
"""
import time
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
TIEMPO_OSCURO = 0.5           # Oscuridad sostenida para ordenar paro seguro.
TIEMPO_SIN_IMAGEN = 1.0

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
camara_lista = False
cajas = []
video = np.zeros((480, 640, 3), dtype=np.uint8)
ventana = 'PiCar-X: 1 Alto / 2 Peaton'
carpeta = Path(__file__).resolve().parent
px = Picarx()

try:
    px.stop()
    px.set_dir_servo_angle(0)  # Trayectoria recta; no es seguimiento de carril.

    alto = cv2.CascadeClassifier(str(carpeta / 'stop_cascade.xml'))
    peaton = cv2.CascadeClassifier(str(carpeta / 'pedestrian_cascade.xml'))
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
            # Vilib publica cada captura en un array nuevo. Conservamos la referencia
            # para no contar varias veces la misma imagen ni confundirla con una nueva.
            imagen_anterior = imagen
            ultima_imagen = ahora
            camara_lista = True
            video = imagen.copy()
            gris = cv2.cvtColor(video, cv2.COLOR_BGR2GRAY)
            brillo = float(np.mean(gris))
            cajas = []

            # 1. Imagen oscura: mide el promedio de intensidad de todos los pixeles.
            if brillo < BRILLO_MINIMO:
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
                    cajas = alto.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=3)
                elif modo == 2:
                    cajas = peaton.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=3)

                detectado = len(cajas) > 0
                if detectado:
                    contador = min(contador + 1, CONFIRMACIONES)
                else:
                    contador = 0
                confirmado = contador >= CONFIRMACIONES

                # 3. MODO 1: detenerse 10 s y luego ignorar esa senal hasta que salga.
                if modo == 1 and estado != 'PARO_SEGURO':
                    if estado == 'ALTO_10S':
                        if ahora - inicio_alto >= TIEMPO_ALTO:
                            estado = 'AVANCE'
                            inicio_despejado = None
                            contador = 0
                    elif not alto_habilitado:
                        if detectado:
                            inicio_despejado = None
                        elif inicio_despejado is None:
                            inicio_despejado = ahora
                        elif ahora - inicio_despejado >= TIEMPO_REARME:
                            alto_habilitado = True
                            inicio_despejado = None
                            contador = 0
                    elif confirmado:
                        estado = 'ALTO_10S'
                        inicio_alto = ahora
                        alto_habilitado = False
                        inicio_despejado = None

                # 4. MODO 2: esperar al peaton y confirmar 2 s sin detecciones.
                elif modo == 2 and estado != 'PARO_SEGURO':
                    if estado == 'AVANCE' and confirmado:
                        estado = 'ESPERA_PEATON'
                        inicio_despejado = None
                    if estado == 'ESPERA_PEATON':
                        if detectado:
                            inicio_despejado = None
                        elif inicio_despejado is None:
                            inicio_despejado = ahora
                        elif ahora - inicio_despejado >= TIEMPO_DESPEJADO:
                            estado = 'AVANCE'
                            inicio_despejado = None
                            contador = 0

            for x, y, w, h in cajas:
                cv2.rectangle(video, (x, y), (x+w, y+h), (0, 255, 0), 2)

        # 5. Si Vilib deja de entregar imagenes nuevas, el paro queda enclavado.
        # Esto comprueba actualizacion de arrays, no que los pixeles cambien:
        # una escena inmovil con camara funcionando NO debe causar un paro.
        if not valida or time.monotonic() - ultima_imagen > TIEMPO_SIN_IMAGEN:
            estado = 'PARO_SEGURO'
            motivo = 'Sin imagen nueva de camara'
            camara_lista = False
            contador = 0
            inicio_despejado = None
            inicio_oscuro = None

        # 6. Mostrar estado, deteccion y brillo (para ajustar el umbral al tapar).
        pantalla = video.copy()
        textos = [f'Modo: {modo} | Estado: {estado}',
                  f'Brillo: {brillo:.1f} | Limite oscuro: {BRILLO_MINIMO}',
                  f'Detecciones: {len(cajas)} | Confirmacion: {contador}/{CONFIRMACIONES}',
                  '1 alto | 2 peaton | W avanzar | ESPACIO/D parar | Q salir']
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
        tecla = cv2.waitKey(10) & 0xFF

        # 7. Teclado: cambiar modo SIEMPRE detiene el carrito.
        if tecla in (ord('q'), ord('Q'), 27):
            break
        if cv2.getWindowProperty(ventana, cv2.WND_PROP_VISIBLE) < 1:
            break
        if tecla in (ord('1'), ord('2')):
            modo = 1 if tecla == ord('1') else 2
            estado = 'PARO_SEGURO'
            motivo = 'Modo seleccionado. Presiona W'
            contador = 0
            alto_habilitado = True
            inicio_alto = None
            inicio_despejado = None
        elif tecla in (32, ord('d'), ord('D')):
            estado = 'PARO_SEGURO'
            motivo = 'Parada manual. Presiona W para reiniciar'
        elif tecla in (ord('w'), ord('W')):
            # No permitir que W salte el alto ni la espera del peaton.
            if (estado == 'PARO_SEGURO' and modo != 0 and camara_lista
                    and brillo >= BRILLO_MINIMO
                    and time.monotonic() - ultima_imagen <= TIEMPO_SIN_IMAGEN):
                estado = 'AVANCE'
                contador = 0
                alto_habilitado = True
                inicio_alto = None
                inicio_despejado = None
                motivo = ''

        # 8. Un solo lugar ordena avanzar. Todos los demas estados detienen.
        if estado == 'AVANCE':
            px.forward(POTENCIA)
        else:
            px.stop()

except KeyboardInterrupt:
    print('Programa interrumpido.')
finally:
    # Si hay un error, Ctrl+C o salida normal, detener antes de cerrar la camara.
    px.stop()
    Vilib.camera_close()
    cv2.destroyAllWindows()
