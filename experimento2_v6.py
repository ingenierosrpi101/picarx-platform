import json
import math
import time
from pathlib import Path
import cv2
from picarx import Picarx
from vilib import Vilib


# ============================================================
# 1. CONFIGURACION
# ============================================================

# Buscar el contorno mas grande en todo el ancho de la imagen.
ROI_X_FIN = 1.0  # Puedes reducirlo para limitar la zona de busqueda.

# Altura de la franja donde se busca el borde.
ROI_Y_INICIO = 0.10
ROI_Y_FIN = 0.55

AREA_MINIMA = 100
TOLERANCIA = 70  # Solo cambia el mensaje en pantalla.
KP = 0.1        # Grados de giro por cada pixel de error.
SIGNO_DIRECCION = 1  # Cambiar a -1 si corrige al lado contrario.
ANGULO_MAX = 25.0
VELOCIDAD = 10   # Potencia de los motores; no indica cm/s.
TIEMPO_MAX_IMAGEN = 1.0

# Teclas: S guardar HSV, C guardar referencia, W avanzar, D/espacio parar,
# T probar direccion sin avance, R recalibrar, Q/Esc salir.
modo = "PARADO"
angulo = 0.0
px = None
ultima_muestra = None
ultimo_cambio_imagen = time.monotonic()


def angulo_proporcional(error):
    giro = SIGNO_DIRECCION * KP * error
    if giro > ANGULO_MAX:
        giro = ANGULO_MAX
    elif giro < -ANGULO_MAX:
        giro = -ANGULO_MAX
    return giro


def parar():
    global modo, angulo
    modo = "PARADO"
    angulo = 0.0
    if px is not None:
        px.stop()
        px.set_dir_servo_angle(0)


ARCHIVO_HSV = Path(__file__).resolve().with_name(
    "calibracion_amarillo.json"
)

VENTANA_VIDEO = "Video Capture"
VENTANA_HSV = "Ajustar HSV"

FUENTE = cv2.FONT_HERSHEY_SIMPLEX

# Valores iniciales del color. Se ajustan con las barras.
hsv_min = [0, 0, 0]
hsv_max = [180, 255, 255]

referencia_borde = None
medidas_anteriores = None

mensaje = "Ajusta HSV y pulsa S"



# Posicion de la camara a partir de su cero calibrado.
# Estos angulos no cambian la calibracion guardada de los servos.
CAM_PAN_INICIAL = 0.0
CAM_TILT_INICIAL = 0.0
PASO_CAMARA = 1.0
CAM_PAN_MIN, CAM_PAN_MAX = -30.0, 30.0
CAM_TILT_MIN, CAM_TILT_MAX = -30.0, 30.0
ARCHIVO_CAMARA = Path(__file__).resolve().with_name("posicion_camara.json")
cam_pan = CAM_PAN_INICIAL
cam_tilt = CAM_TILT_INICIAL


def cargar_posicion_camara():
    global cam_pan, cam_tilt
    if not ARCHIVO_CAMARA.exists():
        return
    try:
        datos = json.loads(ARCHIVO_CAMARA.read_text(encoding="utf-8"))
        pan, tilt = datos["pan"], datos["tilt"]
        for valor, minimo, maximo in (
            (pan, CAM_PAN_MIN, CAM_PAN_MAX),
            (tilt, CAM_TILT_MIN, CAM_TILT_MAX),
        ):
            if (type(valor) not in (int, float) or not math.isfinite(valor)
                    or not minimo <= valor <= maximo):
                raise ValueError("Angulo de camara fuera de rango")
        cam_pan, cam_tilt = float(pan), float(tilt)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("No se cargo posicion de camara:", exc)


def ajustar_camara():
    """Vista en vivo y motores detenidos. Enter guarda; Q sale del programa."""
    global cam_pan, cam_tilt
    global referencia_borde
    global ultima_muestra, ultimo_cambio_imagen
    parar()
    referencia_borde = None
    seleccionado = "tilt"
    aviso = "ENTER guardar y continuar | Q/Esc salir"
    px.set_cam_pan_angle(cam_pan)
    px.set_cam_tilt_angle(cam_tilt)

    while True:
        px.stop()
        original = Vilib.img
        hay_imagen = original is not None and original.size > 0
        if hay_imagen:
            vista = original.copy()
            h, w = vista.shape[:2]
            cv2.rectangle(vista, (0, int(h * ROI_Y_INICIO)),
                          (int(w * ROI_X_FIN) - 1, int(h * ROI_Y_FIN)), (0, 255, 255), 2)
            cv2.circle(vista, (w // 2, int(h * (ROI_Y_INICIO + ROI_Y_FIN) / 2)),
                       7, (255, 0, 0), -1)
            textos = [
                "AJUSTE CAMARA",
                f"2: PAN {cam_pan:+.1f} | 3: TILT {cam_tilt:+.1f}",
                f"Seleccion: {seleccionado} | W/D + | S/A - | paso {PASO_CAMARA}",
                "0: ambos a cero | espacio: detener",
                aviso,
            ]
            for i, texto in enumerate(textos):
                cv2.putText(vista, texto, (10, h - 115 + i * 23),
                            FUENTE, 0.45, (0, 255, 255), 1)
            cv2.imshow(VENTANA_VIDEO, vista)
        key = cv2.waitKey(20) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            return False
        if key == ord("2"):
            seleccionado = "pan"
        elif key == ord("3"):
            seleccionado = "tilt"
        elif key in (ord("w"), ord("W"), ord("d"), ord("D"),
                     ord("s"), ord("S"), ord("a"), ord("A")):
            paso = PASO_CAMARA if key in (ord("w"), ord("W"), ord("d"), ord("D")) else -PASO_CAMARA
            if seleccionado == "pan":
                cam_pan = round(max(CAM_PAN_MIN, min(CAM_PAN_MAX, cam_pan + paso)), 2)
                px.set_cam_pan_angle(cam_pan)
            else:
                cam_tilt = round(max(CAM_TILT_MIN, min(CAM_TILT_MAX, cam_tilt + paso)), 2)
                px.set_cam_tilt_angle(cam_tilt)
        elif key == ord("0"):
            cam_pan = cam_tilt = 0.0
            px.set_cam_pan_angle(cam_pan)
            px.set_cam_tilt_angle(cam_tilt)
        elif key in (10, 13):
            if not hay_imagen:
                print("Espera a tener imagen antes de confirmar la camara.")
                continue
            try:
                temporal = ARCHIVO_CAMARA.with_suffix(".tmp")
                temporal.write_text(json.dumps({"pan": cam_pan, "tilt": cam_tilt}, indent=4), encoding="utf-8")
                temporal.replace(ARCHIVO_CAMARA)
            except OSError as exc:
                print("No se guardaron los angulos:", exc)
                aviso = "Error al guardar: revisa terminal y pulsa ENTER"
                continue
            ultima_muestra = None
            ultimo_cambio_imagen = time.monotonic()
            print(f"Camara guardada: pan={cam_pan}, tilt={cam_tilt}")
            return True


# ============================================================
# 2. CALIBRACION HSV
# ============================================================

def cargar_hsv():
    global hsv_min, hsv_max

    if not ARCHIVO_HSV.exists():
        print("Sin calibracion guardada. Ajusta los sliders.")
        return False

    try:
        datos = json.loads(
            ARCHIVO_HSV.read_text(encoding="utf-8")
        )

        bajos = datos["amarillo"]["min"]
        altos = datos["amarillo"]["max"]

        if not isinstance(bajos, list) or not isinstance(altos, list):
            raise ValueError("Los limites deben ser listas.")

        if len(bajos) != 3 or len(altos) != 3:
            raise ValueError("Se requieren tres valores HSV.")

        for bajo, alto, limite in zip(bajos, altos, (180, 255, 255)):
            if not (
                type(bajo) is int
                and type(alto) is int
                and 0 <= bajo < alto <= limite
            ):
                raise ValueError("Rango HSV invalido.")

        hsv_min = bajos
        hsv_max = altos
        print("HSV cargado:", ARCHIVO_HSV)
        return True

    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("No se pudo cargar HSV:", exc)
        return False


def guardar_hsv():
    datos = {
        "amarillo": {
            "min": hsv_min,
            "max": hsv_max,
        }
    }

    temporal = ARCHIVO_HSV.with_suffix(".tmp")
    temporal.write_text(
        json.dumps(datos, indent=4),
        encoding="utf-8",
    )
    temporal.replace(ARCHIVO_HSV)

    print("HSV guardado:", ARCHIVO_HSV)


def nada(valor):
    pass


def crear_barras():
    cv2.namedWindow(VENTANA_HSV)

    nombres = ("H", "S", "V")
    maximos = (180, 255, 255)

    for i, nombre in enumerate(nombres):
        cv2.createTrackbar(
            "Low " + nombre,
            VENTANA_HSV,
            hsv_min[i],
            maximos[i],
            nada,
        )

        cv2.createTrackbar(
            "High " + nombre,
            VENTANA_HSV,
            hsv_max[i],
            maximos[i],
            nada,
        )


def leer_barras():
    global hsv_min, hsv_max

    bajos = []
    altos = []

    for nombre in ("H", "S", "V"):
        bajo = cv2.getTrackbarPos(
            "Low " + nombre, VENTANA_HSV
        )
        alto = cv2.getTrackbarPos(
            "High " + nombre, VENTANA_HSV
        )

        # Mantener el limite inferior menor al superior.
        alto = max(1, alto)
        bajo = min(bajo, alto - 1)

        cv2.setTrackbarPos(
            "Low " + nombre, VENTANA_HSV, bajo
        )
        cv2.setTrackbarPos(
            "High " + nombre, VENTANA_HSV, alto
        )

        bajos.append(bajo)
        altos.append(alto)

    hsv_min = bajos
    hsv_max = altos


# ============================================================
# 3. SELECCION Y SEGUIMIENTO DEL BORDE
# ============================================================

def elegir_borde(candidatos):
    """Elegir el contorno de mayor area dentro de la ROI."""
    if not candidatos:
        return None

    return max(range(len(candidatos)),
               key=lambda i: cv2.contourArea(candidatos[i][0]))


# ============================================================
# 4. INICIO
# ============================================================

if not 0 < ROI_X_FIN <= 1:
    raise ValueError("El ancho de la ROI no es valido.")

if not 0 <= ROI_Y_INICIO < ROI_Y_FIN <= 1:
    raise ValueError("Los limites de la ROI no son validos.")

calibrando = not cargar_hsv()
mensaje = "Ajusta HSV y pulsa S" if calibrando else "Centra el carrito y pulsa C"

try:
    px = Picarx()
    px.stop()
    px.set_dir_servo_angle(0)
    Vilib.camera_start()
    Vilib.display(local=False, web=True)

    cv2.namedWindow(VENTANA_VIDEO)
    cargar_posicion_camara()
    if not ajustar_camara():
        raise SystemExit(0)
    if calibrando:
        crear_barras()

    inicio_fps = time.monotonic()
    contador_fps = 0
    fps = 0.0

    # ========================================================
    # 5. CICLO PRINCIPAL
    # ========================================================

    while True:
        imagen_camara = Vilib.img

        if imagen_camara is None or imagen_camara.size == 0:
            parar()

            # Leer el teclado aunque no haya imagen.
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), ord("Q"), 27):
                break

            continue

        imagen = imagen_camara.copy()
        # Revisar si la imagen deja de cambiar.
        # Vilib puede conservar la ultima imagen si falla la camara.
        muestra = imagen[::8, ::8].tobytes()
        if muestra != ultima_muestra:
            ultima_muestra = muestra
            ultimo_cambio_imagen = time.monotonic()
        imagen_actual = time.monotonic() - ultimo_cambio_imagen < TIEMPO_MAX_IMAGEN
        if not imagen_actual:
            parar()
            mensaje = "Paro por imagen sin cambios: recoloca, C y luego W"
        alto_imagen, ancho_imagen = imagen.shape[:2]

        if calibrando:
            leer_barras()

        # Borrar los resultados antes de procesar la siguiente imagen.
        error = None
        elegido = None
        referencia_valida = False

        centro_imagen = ancho_imagen / 2

        # ----------------------------------------------------
        # 5.1 REGION DE INTERES
        # ----------------------------------------------------

        x1, x2 = 0, int(ancho_imagen * ROI_X_FIN)
        y1 = int(alto_imagen * ROI_Y_INICIO)
        y2 = int(alto_imagen * ROI_Y_FIN)

        roi = imagen[y1:y2, x1:x2]

        medidas_actuales = (ancho_imagen, alto_imagen, x1, x2, y1, y2)

        if (
            medidas_anteriores is not None
            and medidas_actuales != medidas_anteriores
        ):
            parar()
            referencia_borde = None
            mensaje = "Cambio de ROI/resolucion: centra el carrito y pulsa C"

        medidas_anteriores = medidas_actuales

        # ----------------------------------------------------
        # 5.2 SEPARAR EL COLOR DE LA LINEA
        # ----------------------------------------------------

        imagen_hsv = cv2.cvtColor(
            roi, cv2.COLOR_BGR2HSV
        )

        mascara = cv2.inRange(
            imagen_hsv,
            tuple(hsv_min),
            tuple(hsv_max),
        )

        # ----------------------------------------------------
        # 5.3 CONTORNOS Y CENTROIDES
        # ----------------------------------------------------

        contornos, _ = cv2.findContours(
            mascara,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        candidatos = []

        for contorno in contornos:
            area = cv2.contourArea(contorno)

            if area < AREA_MINIMA:
                continue

            momentos = cv2.moments(contorno)

            if momentos["m00"] == 0:
                continue

            # Ubicar el centro del contorno dentro de la imagen completa.
            cx = momentos["m10"] / momentos["m00"] + x1
            cy = momentos["m01"] / momentos["m00"] + y1

            candidatos.append((contorno, cx, cy))

        # ----------------------------------------------------
        # 5.4 ELEGIR UN SOLO BORDE
        # ----------------------------------------------------

        # Elegir el contorno mas grande en cada imagen.
        elegido = elegir_borde(candidatos)

        if calibrando:
            decision = "CALIBRANDO HSV: pulsa S"

        elif elegido is None:
            decision = "Sin borde: detenido. Cuando vuelva, pulsa W o T"

        elif referencia_borde is None:
            decision = "Centra el carrito y pulsa C"

        else:
            # Posicion actual del centro del contorno.
            x_borde = candidatos[elegido][1]

            # Diferencia respecto a la posicion guardada con C.
            error = x_borde - referencia_borde
            referencia_valida = True

            if error < -TOLERANCIA:
                decision = "Borde a la izquierda de la referencia"
            elif error > TOLERANCIA:
                decision = "Borde a la derecha de la referencia"
            else:
                decision = "Dentro de tolerancia"

        # Calcular el giro con cada error. La tolerancia solo cambia el mensaje.
        if not referencia_valida or not imagen_actual:
            parar()
        angulo = angulo_proporcional(error) if referencia_valida else 0.0
        if modo in ("AVANCE", "PRUEBA") and referencia_valida:
            px.set_dir_servo_angle(angulo)
            if modo == "AVANCE":
                px.forward(VELOCIDAD)
            else:
                px.stop()
        else:
            px.stop()
            px.set_dir_servo_angle(0)

        # ----------------------------------------------------
        # 5.6 DIBUJAR CONTORNOS
        # ----------------------------------------------------

        for i, (contorno, cx, cy) in enumerate(candidatos):
            color = (
                (255, 0, 255)
                if i == elegido
                else (180, 180, 180)
            )

            cv2.drawContours(
                imagen,
                [contorno],
                -1,
                color,
                2,
                offset=(x1, y1),
            )

            cv2.circle(
                imagen,
                (round(cx), round(cy)),
                5,
                color,
                -1,
            )

        # Amarillo: region de interes.
        cv2.rectangle(
            imagen,
            (x1, y1),
            (x2 - 1, y2 - 1),
            (0, 255, 255),
            2,
        )

        # Dibujar las referencias a media altura de la ROI.
        y_puntos = (y1 + y2) // 2

        # Azul: centro horizontal de la imagen; solo es una guia visual.
        cv2.circle(imagen, (round(centro_imagen), y_puntos),
                   7, (255, 0, 0), -1)

        # Verde: posicion horizontal guardada al pulsar C.
        if referencia_borde is not None:
            cv2.circle(imagen, (round(referencia_borde), y_puntos),
                       9, (0, 255, 0), 2)

        # Repintar el centro elegido para que siga visible si coincide con otro punto.
        if elegido is not None:
            _, cx, cy = candidatos[elegido]
            cv2.circle(imagen, (round(cx), round(cy)),
                       5, (255, 0, 255), -1)

        # ----------------------------------------------------
        # 5.7 FPS DEL CICLO
        # ----------------------------------------------------

        # Vilib puede entregar la misma imagen varias veces.
        # Se cuentan las vueltas del ciclo por segundo, no las imagenes nuevas.
        contador_fps += 1
        ahora = time.monotonic()
        transcurrido = ahora - inicio_fps

        if transcurrido >= 1:
            fps = contador_fps / transcurrido
            contador_fps = 0
            inicio_fps = ahora

        # ----------------------------------------------------
        # 5.8 INFORMACION EN PANTALLA
        # ----------------------------------------------------

        cv2.putText(
            imagen, decision,
            (15, 30), FUENTE, 0.55,
            (0, 255, 255), 2,
        )

        cv2.putText(
            imagen,
            f"FPS: {fps:.1f} | Pan {cam_pan:+.0f} Tilt {cam_tilt:+.0f} | M: camara",
            (15, alto_imagen - 100),
            FUENTE, 0.5, (0, 255, 255), 1,
        )

        cv2.putText(
            imagen,
            f"{modo} | P: {angulo:+.1f} grados | Candidatos: {len(candidatos)}",
            (15, alto_imagen - 75),
            FUENTE, 0.5, (0, 255, 255), 1,
        )

        texto_error = (
            "Error: --"
            if error is None
            else f"Error: {error:+.1f} px"
        )

        cv2.putText(
            imagen, texto_error,
            (15, alto_imagen - 50),
            FUENTE, 0.65, (0, 255, 0), 2,
        )

        cv2.putText(
            imagen, mensaje,
            (15, alto_imagen - 20),
            FUENTE, 0.45, (0, 255, 255), 1,
        )

        cv2.imshow(VENTANA_VIDEO, imagen)
        cv2.imshow*("Mascara", mascara)
        # Mostrar la mascara junto a las barras mientras se ajusta el color.
        if calibrando:
            cv2.imshow(VENTANA_HSV, mascara)

        # ----------------------------------------------------
        # 5.9 TECLADO
        # ----------------------------------------------------

        key = cv2.waitKey(1) & 0xFF

        if key in (ord("q"), ord("Q"), 27):
            break

        elif key in (ord("m"), ord("M")):
            if not ajustar_camara():
                break
            mensaje = "Camara ajustada: centra el carrito y pulsa C | M camara"
            inicio_fps = time.monotonic()
            contador_fps = 0
            continue

        elif key in (ord("d"), ord("D"), 32):
            parar()
            mensaje = "Parado | W avanzar | T direccion sin avance"

        elif key in (ord("w"), ord("W"), ord("t"), ord("T")):
            if referencia_valida and imagen_actual and not calibrando:
                modo = "AVANCE" if key in (ord("w"), ord("W")) else "PRUEBA"
                mensaje = "D/espacio: parar | Q: salir"
            else:
                parar()
                mensaje = "Termina HSV con S, centra el carrito y pulsa C"

        elif key in (ord("s"), ord("S")) and calibrando:
            try:
                guardar_hsv()

            except OSError as exc:
                mensaje = "Error al guardar HSV: revisa terminal"
                print(exc)

            else:
                calibrando = False
                cv2.destroyWindow(VENTANA_HSV)
                mensaje = "Centra el carrito y pulsa C | R HSV | Q salir"

        elif key in (ord("c"), ord("C")) and not calibrando:
            parar()
            referencia_borde = None
            indice = elegir_borde(candidatos)
            if indice is not None and imagen_actual:
                referencia_borde = candidatos[indice][1]
                mensaje = "Referencia guardada | W avanzar | T probar | D parar"
                print("Posicion guardada:", referencia_borde)
            else:
                mensaje = "No hay contorno o imagen valida: vuelve a pulsar C"

        elif key in (ord("r"), ord("R")) and not calibrando:
            parar()
            referencia_borde = None

            calibrando = True
            crear_barras()
            mensaje = "Ajusta HSV y pulsa S"

finally:
    try:
        parar()
    finally:
        try:
            cv2.destroyAllWindows()
        finally:
            Vilib.camera_close()
