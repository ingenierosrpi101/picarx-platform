import cv2
import numpy as np
import imutils
from vilib import Vilib
import os
import time

# Iniciar cámara con Vilib
Vilib.camera_start()

# Iniciar visualización (puedes quitarla si solo quieres la ventana de OpenCV)
Vilib.display(local=False, web=True)

Datos = 'p'
if not os.path.exists(Datos):
    print('Carpeta creada: ', Datos)
    os.makedirs(Datos)

x1, y1 = 190, 80
x2, y2 = 450, 398
count = 0

while True:
    # Vilib.img se llena desde un hilo; al inicio puede ser None
    if Vilib.img is None:
        time.sleep(0.01)
        continue

    frame = Vilib.img.copy()
    imAux = frame.copy()

    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
    objeto = imAux[y1:y2, x1:x2]

    k = cv2.waitKey(1)
    if k == ord('s'):
        cv2.imwrite(Datos + '/objeto_{}.jpg'.format(count), objeto)
        print('Imagen guardada:' + '/objeto_{}.jpg'.format(count))
        count = count + 1
    if k == 27:
        break

    cv2.imshow('frame', frame)

Vilib.camera_close()
cv2.destroyAllWindows()