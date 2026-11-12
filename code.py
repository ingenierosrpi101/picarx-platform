import cv2
import os
from time import sleep
from vilib import Vilib

Datos = 'p'

# Iniciar cámara con Vilib
Vilib.camera_start()
Vilib.display(local=False, web=True)

if not os.path.exists(Datos):
    print('Carpeta creada: ', Datos)
    os.makedirs(Datos)

x1, y1 = 190, 80
x2, y2 = 450, 398
count = 0

while True:
    comando = input("s: guardar | q: salir: ")

    if comando == "q":
        break

    if comando == "s":
        frame = Vilib.img

        if frame is not None:
            objeto = frame[y1:y2, x1:x2]
            ruta = Datos + '/objeto_{}.jpg'.format(count)
            cv2.imwrite(ruta, objeto)
            print('Imagen guardada: ' + ruta)
            count += 1
        else:
            print("Error: No se pudo leer el frame de la cámara")

    sleep(0.1)

Vilib.camera_close()