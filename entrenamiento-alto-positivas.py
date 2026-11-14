import cv2
import os
import numpy as np
from vilib import Vilib

Datos = 'p - alto'
x1, y1 = 215, 120
x2, y2 = 460, 360
FUENTE = cv2.FONT_HERSHEY_SIMPLEX

if not os.path.exists(Datos):
    print('Carpeta creada: ', Datos)
    os.makedirs(Datos)


def obtener_frame():
    """Convierte Vilib.img (ListProxy) en un arreglo NumPy BGR, o None."""
    img = Vilib.img
    if img is None:
        return None
    try:
        frame = np.array(img[:], dtype=np.uint8)  # [:] trae una lista real
    except Exception:
        return None
    # Si la imagen viene envuelta en una lista de un elemento: (1, alto, ancho, 3)
    if frame.ndim == 4 and frame.shape[0] == 1:
        frame = frame[0]
    # Una imagen válida tiene 3 dimensiones: (alto, ancho, canales)
    if frame.ndim != 3:
        return None
    return frame


count = 0

try:
    Vilib.camera_start()
    Vilib.display(local=False, web=True)

    while True:
        imAux = obtener_frame()

        if imAux is None:
            key = cv2.waitKey(10) & 0xFF
            if key == ord("q") or key == 27:
                break
            continue

        frame = imAux.copy()  # copia con dibujos para mostrar

        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
        cv2.putText(frame, f"Guardadas: {count}  |  s: guardar  q/Esc: salir",
                    (10, 25), FUENTE, 0.6, (0, 255, 0), 2, cv2.LINE_AA)

        cv2.imshow('frame', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            objeto = imAux[y1:y2, x1:x2]
            ruta = Datos + '/objeto_{}.jpg'.format(count)
            cv2.imwrite(ruta, objeto)
            print('Imagen guardada: ' + ruta)
            count += 1
        elif key == ord('q') or key == 27:
            break

finally:
    try:
        cv2.destroyAllWindows()
    finally:
        Vilib.camera_close()