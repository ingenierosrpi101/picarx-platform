import cv2
from vilib import Vilib
import os
import time

Datos = 'n'

# Iniciar cámara con Vilib
Vilib.camera_start()

# Iniciar visualización (puedes quitarla si solo quieres la ventana de OpenCV)
Vilib.display(local=False, web=True)

if not os.path.exists(Datos):
    print('Carpeta creada: ', Datos)
    os.makedirs(Datos)

count = 0

while True:
    # Vilib.img se llena desde un hilo; al inicio puede ser None
    if Vilib.img is None:
        time.sleep(0.01)
        continue

    frame = Vilib.img.copy()

    k = cv2.waitKey(1)
    if k == ord('s'):
        cv2.imwrite(Datos + '/objeto_{}.jpg'.format(count), frame)
        print('Imagen guardada:' + '/objeto_{}.jpg'.format(count))
        count = count + 1
    if k == 27:
        break

    cv2.imshow('frame', frame)

Vilib.camera_close()
cv2.destroyAllWindows()