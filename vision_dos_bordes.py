"""
Detección por color con Vilib y OpenCV.
Flujo: imagen → ROI → HSV → borde izquierdo → error respecto a su posicion deseada.
Solo muestra resultados: todavía no controla motores.
S: guardar HSV. R: recalibrar. C: fijar referencia del borde con el carrito centrado.
El JSON HSV se carga al iniciar. La referencia C se fija en cada ejecucion.
Si pierde el borde, recoloca el carrito centrado y pulsa C para reiniciar.
Salir: tecla q o Esc con una ventana de OpenCV seleccionada.
"""

# 1. LIBRERÍAS
import json
from pathlib import Path
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

# Umbral inicial para el rectangulo mas pequeno; no es un valor universal.
# Aumentarlo descarta MAS contornos; reducirlo acepta regiones mas pequenas.
AREA_MINIMA = 100        # Area minima de cada contorno, en pixeles cuadrados.
ROI_Y_INICIO = 0.15      # 15 % del alto: ajustar segun la camara.
ROI_Y_FIN = 0.30         # 30 % del alto. Todo el ancho de la imagen.
TOLERANCIA = 70          # Error entre -70 y +70 se considera centrado.
# Asociacion temporal del mismo borde: valores iniciales, ajustables.
SALTO_MAXIMO_PX = 96  # Maximo cambio de cx entre imagenes, para 640 px de ancho.
MARGEN_ASOCIACION_PX = 20  # Rechazar dos candidatos casi igual de cercanos.
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


# 4. GUARDAR Y RECUPERAR LA CALIBRACIÓN
# __file__ coloca el JSON junto al script, aunque se ejecute desde otra carpeta.
ARCHIVO_HSV = Path(__file__).resolve().with_name("calibracion_amarillo.json")
calibrando = True
mensaje = "Calibrando amarillo: S guardar"


def cargar_calibracion():
    global low_H, low_S, low_V, high_H, high_S, high_V
    if not ARCHIVO_HSV.exists():
        print("Sin JSON previo: ajusta los sliders y presiona S.")
        return
    try:
        datos = json.loads(ARCHIVO_HSV.read_text(encoding="utf-8"))
        bajos = datos["amarillo"]["min"]
        altos = datos["amarillo"]["max"]
        if not isinstance(bajos, list) or not isinstance(altos, list):
            raise ValueError("min y max deben ser listas")
        if len(bajos) != 3 or len(altos) != 3:
            raise ValueError("Se necesitan tres valores H, S, V por limite")
        for bajo, alto, limite in zip(bajos, altos, (max_value_H, 255, 255)):
            if not (type(bajo) is int and type(alto) is int
                    and 0 <= bajo < alto <= limite):
                raise ValueError("Rango HSV invalido")
        # Asignar solo despues de validar todos los valores.
        low_H, low_S, low_V = bajos
        high_H, high_S, high_V = altos
        print(f"Calibracion cargada: {ARCHIVO_HSV}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"No se pudo cargar la calibracion: {exc}. Ajusta los sliders.")


def guardar_calibracion():
    datos = {"amarillo": {
        "min": [low_H, low_S, low_V],
        "max": [high_H, high_S, high_V]
    }}
    # Escribir primero en un temporal y reemplazar al terminar.
    temporal = ARCHIVO_HSV.with_suffix(".tmp")
    temporal.write_text(json.dumps(datos, indent=4), encoding="utf-8")
    temporal.replace(ARCHIVO_HSV)
    print(f"Calibracion guardada: {ARCHIVO_HSV}")


def crear_sliders():
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


def elegir_borde(xs, x_anterior, ancho):
    """Devuelve indice del candidato cercano o None si no es identificable.
    La proximidad es una heuristica: no reconoce semanticamente la pista.
    """
    if not xs:
        return None
    distancias = sorted((abs(x - x_anterior), i) for i, x in enumerate(xs))
    if distancias[0][0] > SALTO_MAXIMO_PX * ancho / 640:
        return None
    if len(distancias) > 1:
        if distancias[1][0] - distancias[0][0] < MARGEN_ASOCIACION_PX * ancho / 640:
            return None
    return distancias[0][1]


x_deseada = None
x_anterior = None
borde_perdido = False
geometria_anterior = None


# 4. CÁMARA, VENTANAS Y SLIDERS
# try/finally permite cerrar los recursos también al presionar Ctrl+C
# o si ocurre un error durante la ejecución.
cargar_calibracion()

try:
    Vilib.camera_start()
    # Conserva la transmisión web. Las ventanas locales las crea OpenCV.
    Vilib.display(local=False, web=True)

    cv2.namedWindow(window_capture_name)
    cv2.namedWindow(window_detection_name)

    crear_sliders()

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
            if x_deseada is not None:
                borde_perdido = True
            # Aunque no haya imagen, atender teclado y ventanas.
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                break
            continue

        frame = frame_vilib.copy()
        height, width = frame.shape[:2]  # Alto y ancho en píxeles.

        # Reiniciar por imagen para no conservar una decisión anterior
        # cuando ya no se encuentre un contorno válido.
        decision = "SIN REFERENCIA: pulsa C"
        error = None

        # 6.2 Rectangulo comun para ambos limites amarillos.
        # Todo el ancho evita recortar los lados como en la ROI anterior.
        x1, x2 = 0, width
        y1 = int(height * ROI_Y_INICIO)
        y2 = int(height * ROI_Y_FIN)

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

        # 6.5 Filtrar UNICAMENTE por area y momentos no nulos.
        # No exigimos altura minima: una marca inclinada sigue siendo candidata.
        # No dividir la imagen en mitades: ambos limites pueden desplazarse.
        candidatos = []
        for c in contornos:
            if cv2.contourArea(c) < AREA_MINIMA:
                continue
            M = cv2.moments(c)
            if M["m00"] == 0:
                continue
            # Coordenadas de ROI -> coordenadas de imagen completa.
            cx = M["m10"] / M["m00"] + x1
            cy = M["m01"] / M["m00"] + y1
            candidatos.append((c, cx, cy))

        # Dibujar candidatos incluso si falta uno, para facilitar las pruebas.
        for c, cx, cy in candidatos:
            cv2.drawContours(frame, [c], -1, (180, 180, 180), 1, offset=(x1, y1))

        # La referencia depende de resolucion y ROI. Reiniciar si cambian.
        geometria = (width, height, x1, x2, y1, y2)
        if geometria_anterior is not None and geometria != geometria_anterior:
            x_deseada = x_anterior = None
            borde_perdido = False
        geometria_anterior = geometria
        elegido = None
        if x_deseada is None:
            # Vista previa: candidato mas a la izquierda.
            # Verifica visualmente que sea el borde antes de pulsar C.
            if candidatos:
                elegido = min(range(len(candidatos)), key=lambda i: candidatos[i][1])
            decision = "Guarda HSV con S" if calibrando else "C: fijar borde izquierdo"
        elif borde_perdido:
            decision = "BORDE PERDIDO: recoloca y pulsa C"
        else:
            elegido = elegir_borde([c[1] for c in candidatos], x_anterior, width)
            if elegido is None:
                borde_perdido = True
                decision = "BORDE PERDIDO: recoloca y pulsa C"
            else:
                x_anterior = candidatos[elegido][1]
                # NO se calcula el centro del carril ni un ancho anterior.
                error = x_anterior - x_deseada
                if error < -TOLERANCIA:
                    decision = "Borde a la izquierda de referencia"
                elif error > TOLERANCIA:
                    decision = "Borde a la derecha de referencia"
                else:
                    decision = "Borde dentro de tolerancia"

        # Todos los centroides se dibujan, incluso cuando no hay error valido.
        for i, (c, cx, cy) in enumerate(candidatos):
            color = (255, 0, 255) if i == elegido else (180, 180, 180)
            cv2.drawContours(frame, [c], -1, color, 2, offset=(x1, y1))
            cv2.circle(frame, (round(cx), round(cy)), 6, color, -1)
        if x_deseada is not None:
            # Azul: posicion deseada DEL BORDE, no centro de imagen.
            cv2.line(frame, (round(x_deseada), y1), (round(x_deseada), y2),
                     (255, 0, 0), 2)
            cv2.putText(frame, f"Referencia borde x={x_deseada:.1f}",
                        (20, height - 75), FUENTE, 0.55, (255, 150, 0), 1)
            if error is not None:
                y_ref = (y1 + y2) // 2
                cv2.line(frame, (round(x_deseada), y_ref),
                         (round(x_anterior), y_ref), (0, 255, 0), 2)

        cv2.putText(frame, f"Contornos: {len(contornos)} | Validos: {len(candidatos)}",
                    (20, height - 50), FUENTE, 0.55, (0, 255, 255), 1)
        texto_error = "Error: --" if error is None else f"Error: {error:+.1f} px"
        cv2.putText(frame, texto_error, (20, height - 20),
                    FUENTE, 0.65, (0, 255, 0), 2)

        # 6.8 Dibujar ROI y decisión, incluso cuando no hay línea.
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(
            frame, decision, (20, 40),
            FUENTE, 0.65, (0, 255, 255), 2
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

        cv2.putText(frame, mensaje, (20, 115),
                    FUENTE, 0.55, (0, 255, 255), 1)

        # 6.10 Mostrar imagen anotada y máscara de color.
        cv2.imshow(window_capture_name, frame)
        # Tras guardar, mostrar la máscara en una ventana sin sliders.
        if calibrando:
            cv2.imshow(window_detection_name, frame_threshold)
        else:
            cv2.imshow("Mascara amarilla", frame_threshold)

        # Procesar eventos de las ventanas y leer una tecla.
        # 1 ms es la espera solicitada; la real depende del sistema.
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q") or key == 27:  # 27 = Esc.
            break
        elif key in (ord("s"), ord("S")) and calibrando:
            try:
                guardar_calibracion()
            except OSError as exc:
                mensaje = "Error al guardar. Revisa terminal y pulsa S otra vez."
                print(f"No se guardo el JSON: {exc}")
            else:
                calibrando = False
                cv2.destroyWindow(window_detection_name)
                mensaje = "C fija referencia / R recalibrar / Q salir"
        elif key in (ord("c"), ord("C")) and not calibrando:
            if candidatos:
                # Pulsa C SOLO al estar bien colocado y ver el borde izquierdo.
                seleccionado = min(candidatos, key=lambda item: item[1])
                x_deseada = x_anterior = seleccionado[1]
                borde_perdido = False
                print(f"Referencia izquierda fijada en x={x_deseada:.1f}")
            else:
                mensaje = "No hay candidato para fijar. Revisa mascara."
        elif key in (ord("r"), ord("R")) and not calibrando:
            x_deseada = x_anterior = None
            borde_perdido = False
            cv2.destroyWindow("Mascara amarilla")
            crear_sliders()
            calibrando = True
            mensaje = "Calibrando amarillo: S guardar"

# 7. CERRAR RECURSOS AL TERMINAR
finally:
    try:
        cv2.destroyAllWindows()
    finally:
        Vilib.camera_close()

