import cv2
import numpy as np
from vilib import Vilib

haar = cv2.CascadeClassifier('pedestrian_cascade_v2.xml')
font = cv2.FONT_HERSHEY_SIMPLEX


if haar.empty():
    raise FileNotFoundError("No se pudo cargar 'cascade.xml'")


def obtener_frame():
    img = Vilib.img
    if img is None:
        return None
    try:
        frame = np.array(img[:], dtype=np.uint8)
    except Exception:
        return None
    if frame.ndim == 4 and frame.shape[0] == 1:
        frame = frame[0]
    if frame.ndim != 3:
        return None
    return frame


try:
    Vilib.camera_start()
    Vilib.display(local=False, web=True)

    while True:
        frame = obtener_frame()

        if frame is None:
            if cv2.waitKey(10) & 0xFF == ord('q'):
                break
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        prueba = haar.detectMultiScale(gray, 1.07, 2, 0)

        for (x, y, w, h) in prueba:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
            cv2.rectangle(frame, (x, y), (x + 100, y + 40), (255, 0, 0), -1)
            cv2.putText(frame, 'Peaton', (x + 10, y + 30), font, 0.7,
                        (255, 255, 255), 2)

        cv2.imshow('Video', frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

finally:
    try:
        cv2.destroyAllWindows()
    finally:
        Vilib.camera_close()
