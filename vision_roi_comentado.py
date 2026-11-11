"""
Detección por color con Vilib y OpenCV.
Flujo: imagen → ROI → filtro HSV → contorno mayor → centroide → decisión.
Solo muestra resultados: todavía no controla motores.
Salir: tecla q o Esc con una ventana de OpenCV seleccionada.
"""

# 1. LIBRERÍAS
import time                      # Reloj para medir los FPS del ciclo.
import cv2                       # Procesamiento de imágenes y ventanas.
from vilib import Vilib          # Captura de imágenes de la cámara.


# 2. AJUSTES
# HSV: H = tono; S = saturación; V = brillo.
# Conservamos el límite superior 180 de tu slider: incluye todos los tonos.
max_value = 255
max_value_H = 180

# Al iniciar, este rango acepta todos los colores.
# Ajusta los sliders para aislar el color de la línea.
low_H, low_S, low_V = 0, 0, 0
high_H, high_S, high_V = max_value_H, max_value, max_value

AREA_MINIMA = 3000       # Área del contorno en píxeles cuadrados.
TOLERANCIA = 70          # Error entre -70 y +70 se considera centrado.
FUENTE = cv2.FONT_HERSHEY_SIMPLEX

window_capture_name = "Video Capture"
window_detection_name = "Object Detection"

low_H_name, high_H_name = "Low H", "High H"
low_S_name, high_S_name = "Low S", "High S"
low_V_name, high_V_name = "Low V", "High V"


# 3. FUNCIONES DE LOS SLIDERS
# OpenCV ejecuta la función correspondiente cuando mueves un slider.
# val es la posición nueva. global permite modificar la variable externa.
# min/max evitan que el límite inferior alcance o supere al superior.
# setTrackbarPos devuelve el slider al límite permitido si hace falta.

def on_low_H_thresh_trackbar(val):
    global low_H
    low_H = min(high_H - 1, val)
    cv2.setTrackbarPos(low_H_name, window_detection_name, low_H)


def on_high_H_thresh_trackbar(val):
    global high_H
    high_H = max(val, low_H + 1)
    cv2.setTrackbarPos(high_H_name, window_detection_name, high_H)


def on_low_S_thresh_trackbar(val):
    global low_S
    low_S = min(high_S - 1, val)
    cv2.setTrackbarPos(low_S_name, window_detection_name, low_S)


def on_high_S_thresh_trackbar(val):
    global high_S
    high_S = max(val, low_S + 1)
    cv2.setTrackbarPos(high_S_name, window_detection_name, high_S)


def on_low_V_thresh_trackbar(val):
    global low_V
    low_V = min(high_V - 1, val)
    cv2.setTrackbarPos(low_V_name, window_detection_name, low_V)


def on_high_V_thresh_trackbar(val):
    global high_V
    high_V = max(val, low_V + 1)
    cv2.setTrackbarPos(high_V_name, window_detection_name, high_V)


# 4. CÁMARA, VENTANAS Y SLIDERS
# try/finally permite cerrar los recursos también al presionar Ctrl+C
# o si ocurre un error durante la ejecución.
try:
    Vilib.camera_start()
    # Conserva la transmisión web. Las ventanas locales las crea OpenCV.
    Vilib.display(local=False, web=True)

    cv2.namedWindow(window_capture_name)
    cv2.namedWindow(window_detection_name)

    # Argumentos: nombre, ventana, valor inicial, máximo, función asociada.
    cv2.createTrackbar(low_H_name, window_detection_name,
                      low_H, max_value_H, on_low_H_thresh_trackbar)
    cv2.createTrackbar(high_H_name, window_detection_name,
                      high_H, max_value_H, on_high_H_thresh_trackbar)
    cv2.createTrackbar(low_S_name, window_detection_name,
                      low_S, max_value, on_low_S_thresh_trackbar)
    cv2.createTrackbar(high_S_name, window_detection_name,
                      high_S, max_value, on_high_S_thresh_trackbar)
    cv2.createTrackbar(low_V_name, window_detection_name,
                      low_V, max_value, on_low_V_thresh_trackbar)
    cv2.createTrackbar(high_V_name, window_detection_name,
                      high_V, max_value, on_high_V_thresh_trackbar)

    # 5. VARIABLES DEL CONTADOR DE FPS
    inicio_fps = time.monotonic()
    contador_fps = 0
    fps = 0.0

    # 6. CICLO PRINCIPAL: REPETIR EL PROCESAMIENTO
    while True:
        # 6.1 Leer la imagen disponible y trabajar sobre una copia.
        # La copia evita dibujar directamente sobre la imagen compartida.
        frame_vilib = Vilib.img

        if frame_vilib is None:
            # Aunque no haya imagen, atender teclado y ventanas.
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                break
            continue

        frame = frame_vilib.copy()
        height, width = frame.shape[:2]  # Alto y ancho en píxeles.

        # Reiniciar por imagen para no conservar una decisión anterior
        # cuando ya no se encuentre un contorno válido.
        decision = "SIN LINEA"

        # 6.2 Recortar la región de interés (ROI).
        # x: del 15 % al 85 % del ancho.
        # y: del 25 % al 85 % del alto.
        x1 = int(width * 0.15)
        x2 = int(width * 0.85)
        y1 = int(height * 0.25)
        y2 = int(height * 0.85)

        # Las imágenes se indexan así: [filas (y), columnas (x)].
        roi = frame[y1:y2, x1:x2]

        # 6.3 Filtrar el color únicamente dentro de la ROI.
        frame_HSV = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        frame_threshold = cv2.inRange(
            frame_HSV,
            (low_H, low_S, low_V),
            (high_H, high_S, high_V)
        )
        # La máscara resultante es blanca donde el color cumple el rango
        # y negra donde no lo cumple.

        # 6.4 Encontrar los bordes de las manchas blancas.
        contornos, _ = cv2.findContours(
            frame_threshold,
            cv2.RETR_EXTERNAL,       # Solo bordes externos.
            cv2.CHAIN_APPROX_SIMPLE  # Simplifica puntos del contorno.
        )

        if contornos:
            # Escoger una sola referencia: la mancha de mayor área.
            # Es una suposición inicial; la mayor no siempre será la línea.
            c = max(contornos, key=cv2.contourArea)
            area = cv2.contourArea(c)

            if area > AREA_MINIMA:
                # 6.5 Calcular el centroide usando momentos del contorno.
                M = cv2.moments(c)

                # Evitar división entre cero sin saltar el dibujo/teclado.
                if M["m00"] != 0:
                    # El centroide se obtiene en coordenadas de la ROI.
                    # Sumar x1/y1 lo ubica en la imagen completa.
                    x = int(M["m10"] / M["m00"]) + x1
                    y = int(M["m01"] / M["m00"]) + y1

                    # 6.6 Comparar su posición con el centro de la imagen.
                    centro_imagen = width // 2
                    error = x - centro_imagen

                    # Error negativo: objeto a la izquierda.
                    # Error positivo: objeto a la derecha.
                    if error < -TOLERANCIA:
                        decision = "Izquierda"
                    elif error > TOLERANCIA:
                        decision = "Derecha"
                    else:
                        decision = "Centro"

                    # 6.7 Dibujar centroide y coordenadas.
                    # Los colores de dibujo están en orden BGR.
                    cv2.circle(frame, (x, y), 7, (0, 255, 0), -1)
                    cv2.putText(
                        frame, f"{x},{y}", (x + 10, y),
                        FUENTE, 0.75, (0, 255, 0), 1, cv2.LINE_AA
                    )

                    # convexHull crea una envolvente convexa alrededor
                    # del contorno. Solo se usa para dibujar; el centroide
                    # anterior se calculó con el contorno original c.
                    nuevoContorno = cv2.convexHull(c)
                    nuevoContorno[:, :, 0] += x1
                    nuevoContorno[:, :, 1] += y1
                    cv2.drawContours(
                        frame, [nuevoContorno], 0, (255, 0, 0), 3
                    )

        # 6.8 Dibujar ROI y decisión, incluso cuando no hay línea.
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(
            frame, decision, (20, 40),
            FUENTE, 1, (0, 255, 255), 2
        )

        # 6.9 Medir las vueltas con imagen por segundo.
        # Estos son FPS del ciclo, no necesariamente imágenes nuevas:
        # Vilib.img puede contener el mismo fotograma entre dos vueltas.
        contador_fps += 1
        ahora = time.monotonic()
        transcurrido = ahora - inicio_fps

        if transcurrido >= 1:
            fps = contador_fps / transcurrido
            contador_fps = 0
            inicio_fps = ahora

        cv2.putText(
            frame, f"FPS: {fps:.1f}", (20, 80),
            FUENTE, 0.7, (0, 255, 0), 2
        )

        # 6.10 Mostrar imagen anotada y máscara de color.
        cv2.imshow(window_capture_name, frame)
        cv2.imshow(window_detection_name, frame_threshold)

        # Procesar eventos de las ventanas y leer una tecla.
        # 1 ms es la espera solicitada; la real depende del sistema.
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q") or key == 27:  # 27 = Esc.
            break

# 7. CERRAR RECURSOS AL TERMINAR
finally:
    try:
        cv2.destroyAllWindows()
    finally:
        Vilib.camera_close()

