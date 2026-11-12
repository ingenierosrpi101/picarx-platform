"""PiCar-X: calibrar dos colores y visualizar el centro aproximado del carril.

python carril_hsv.py             -> solo vision
python carril_hsv.py --motores   -> permite prueba recta de hasta 2 segundos

S: guardar amarillo, despues blanco. P: prueba recta (solo con --motores).
D o espacio: detener. R: recalibrar. Q o Esc: salir.
Selecciona una ventana OpenCV para que reciba las teclas.
El JSON se crea junto a este programa. No incluye seguimiento de direccion.
"""
import argparse
import json
import time
from pathlib import Path

import cv2

ARCHIVO = Path(__file__).resolve().with_name("calibracion_hsv.json")
# Valores iniciales orientativos: debes comprobarlos con la iluminacion real.
INICIALES = {
    "amarillo": {"min": [18, 90, 80], "max": [40, 255, 255]},
    "blanco": {"min": [0, 0, 170], "max": [179, 70, 255]},
}
# ROI de todo el ancho, entre el 60 y el 75 por ciento del alto.
# Ajustar para que AMBAS marcas crucen claramente el rectangulo.
ROI_Y1, ROI_Y2 = 0.60, 0.75
AREA_MINIMA = 100  # px cuadrados; valor inicial para esta ROI pequena.
VELOCIDAD = 20
DURACION_PRUEBA = 2.0
VIDEO = "Carril - S guardar / P avanzar / D parar / R calibrar / Q salir"
CONTROL = "Calibracion HSV"
BARRAS = ("H min", "S min", "V min", "H max", "S max", "V max")


def rango_valido(r):
    if not isinstance(r, dict):
        return False
    lo, hi = r.get("min"), r.get("max")
    if not isinstance(lo, list) or not isinstance(hi, list):
        return False
    if len(lo) != 3 or len(hi) != 3:
        return False
    return all(type(a) is int and type(b) is int and 0 <= a <= b <= limite
               for a, b, limite in zip(lo, hi, (179, 255, 255)))


def cargar():
    datos = json.loads(json.dumps(INICIALES))
    if ARCHIVO.exists():
        try:
            guardados = json.loads(ARCHIVO.read_text(encoding="utf-8"))
            for color in datos:
                if rango_valido(guardados.get(color)):
                    datos[color] = guardados[color]
                else:
                    print(f"Rango {color} ausente/invalido: usa valores iniciales.")
        except (ValueError, OSError, AttributeError) as exc:
            print(f"No se pudo cargar JSON: {exc}. Revisa la calibracion.")
    return datos


def guardar(datos):
    # Reemplazo atomico: no dejar un JSON incompleto si falla la escritura.
    temporal = ARCHIVO.with_suffix(".tmp")
    temporal.write_text(json.dumps(datos, indent=2), encoding="utf-8")
    temporal.replace(ARCHIVO)


def crear_sliders(rango):
    cv2.namedWindow(CONTROL)
    for nombre, valor, limite in zip(BARRAS, rango["min"] + rango["max"],
                                     (179, 255, 255, 179, 255, 255)):
        cv2.createTrackbar(nombre, CONTROL, valor, limite, lambda valor: None)


def leer_sliders():
    valores = [cv2.getTrackbarPos(nombre, CONTROL) for nombre in BARRAS]
    return {"min": valores[:3], "max": valores[3:]}


def detectar(hsv, rango):
    """Mascara -> contorno de mayor area -> centroide en coordenadas ROI."""
    mascara = cv2.inRange(hsv, tuple(rango["min"]), tuple(rango["max"]))
    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        return mascara, None
    contorno = max(contornos, key=cv2.contourArea)
    if cv2.contourArea(contorno) < AREA_MINIMA:
        return mascara, None
    momentos = cv2.moments(contorno)
    if momentos["m00"] == 0:
        return mascara, None
    cx = momentos["m10"] / momentos["m00"]
    cy = momentos["m01"] / momentos["m00"]
    return mascara, (contorno, cx, cy)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--motores", action="store_true")
    args = parser.parse_args()
    from vilib import Vilib

    px = None
    calibrando = True
    indice = 0
    colores = ("amarillo", "blanco")
    datos = cargar()
    fin_avance = None
    aviso = "Ajusta amarillo. S guarda."

    def detener():
        nonlocal fin_avance
        if px is not None:
            px.stop()
        fin_avance = None

    try:
        if args.motores:
            from picarx import Picarx
            px = Picarx()
            px.stop()
            # reset ya se usa en tu programa; coloca los servos en su cero.
            # Comprueba la orientacion de camara y ruedas ANTES de calibrar.
            px.reset()
        Vilib.camera_start()
        Vilib.display(local=False, web=True)
        cv2.namedWindow(VIDEO)
        crear_sliders(datos["amarillo"])
        print(__doc__)
        print(f"Archivo de calibracion: {ARCHIVO}")

        while True:
            if fin_avance is not None and time.monotonic() >= fin_avance:
                detener()
                aviso = "Prueba terminada. P permite otra prueba."
            frame_vilib = Vilib.img
            if frame_vilib is None or frame_vilib.size == 0:
                detener()
                key = cv2.waitKey(10) & 0xFF
                if key in (ord("q"), 27):
                    break
                continue
            frame = frame_vilib.copy()
            alto, ancho = frame.shape[:2]
            y1, y2 = int(alto * ROI_Y1), int(alto * ROI_Y2)
            roi = frame[y1:y2, :]
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

            rango_actual = None
            if calibrando:
                rango_actual = leer_sliders()
                mascara = cv2.inRange(hsv, tuple(rango_actual["min"]),
                                     tuple(rango_actual["max"]))
                cv2.imshow(CONTROL, mascara)
                aviso = f"Calibrar {colores[indice]} - S guardar"
                if not rango_valido(rango_actual):
                    aviso = "Corrige sliders: cada minimo debe ser <= maximo"

            resultados = {}
            for color, tinta in (("blanco", (255, 0, 255)),
                                 ("amarillo", (0, 255, 255))):
                rango = rango_actual if calibrando and color == colores[indice] else datos[color]
                mascara, resultado = detectar(hsv, rango)
                resultados[color] = resultado
                cv2.imshow("Mascara " + color, mascara)
                if resultado is not None:
                    contorno, cx, cy = resultado
                    cv2.drawContours(frame, [contorno], -1, tinta, 2, offset=(0, y1))
                    punto = (round(cx), round(cy) + y1)
                    cv2.circle(frame, punto, 6, tinta, -1)
                    cv2.putText(frame, color, (punto[0] + 8, punto[1]),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, tinta, 1)

            blanco, amarillo = resultados["blanco"], resultados["amarillo"]
            valido = (blanco is not None and amarillo is not None
                      and blanco[1] < amarillo[1])
            medicion = "SIN REFERENCIA VALIDA"
            if valido:
                # Promedio HORIZONTAL. La altura de dibujo es solo visual.
                centro = (blanco[1] + amarillo[1]) / 2
                error = centro - ancho / 2
                y_dibujo = (y1 + y2) // 2
                cv2.circle(frame, (round(centro), y_dibujo), 8, (0, 255, 0), -1)
                cv2.line(frame, (ancho // 2, y_dibujo), (round(centro), y_dibujo),
                         (0, 255, 0), 2)
                medicion = f"Centro: {centro:.1f} px | Error: {error:+.1f} px"
            elif fin_avance is not None:
                detener()
                aviso = "Parado: referencia perdida. P para reiniciar."

            cv2.rectangle(frame, (0, y1), (ancho - 1, y2 - 1), (255, 150, 0), 2)
            cv2.line(frame, (ancho // 2, y1), (ancho // 2, y2), (255, 150, 0), 1)
            estado = "AVANCE RECTO" if fin_avance is not None else "DETENIDO"
            for i, texto in enumerate((aviso, medicion, estado)):
                cv2.putText(frame, texto, (10, 25 + i * 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1)
            cv2.imshow(VIDEO, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key in (ord("d"), ord(" ")):
                detener()
                aviso = "Detenido manualmente."
            elif key == ord("s") and calibrando and rango_valido(rango_actual):
                datos[colores[indice]] = rango_actual
                try:
                    guardar(datos)
                except OSError as exc:
                    print(f"No se guardo: {exc}. Corrige permisos y pulsa S otra vez.")
                    continue
                print(f"Guardado {colores[indice]}: {rango_actual}")
                cv2.destroyWindow(CONTROL)
                if indice == 0:
                    indice = 1
                    crear_sliders(datos["blanco"])
                else:
                    calibrando = False
                    aviso = "Listo. P prueba recta / R recalibrar / Q salir"
            elif key == ord("r") and not calibrando:
                detener()
                indice = 0
                calibrando = True
                crear_sliders(datos["amarillo"])
            elif key == ord("p") and not calibrando and fin_avance is None:
                if px is None:
                    aviso = "Solo vision. Ejecuta con --motores para probar avance."
                elif not valido:
                    aviso = "No avanza: faltan limites validos."
                else:
                    fin_avance = time.monotonic() + DURACION_PRUEBA
                    px.forward(VELOCIDAD)
                    aviso = "Prueba recta, sin correccion. D o espacio detiene."
    finally:
        try:
            detener()
        finally:
            try:
                cv2.destroyAllWindows()
            finally:
                Vilib.camera_close()


if __name__ == "__main__":
    main()
