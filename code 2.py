import cv2
import os
from time import sleep
from vilib import Vilib

Datos = 'n'

# Iniciar cámara con Vilib
Vilib.camera_start()
Vilib.display(local=False, web=True)

if not os.path.exists(Datos):
    print('Carpeta creada: ', Datos)
    os.makedirs(Datos)

count = 0

while True:
    comando = input("s: guardar | q: salir: ")

    if comando == "q":
        break

    if comando == "s":
        # Se lee el frame DESPUÉS del input, para guardar la imagen actual
        frame = Vilib.img

        if frame is not None:
            ruta = Datos + '/objeto_{}.jpg'.format(count)
            cv2.imwrite(ruta, frame)
            print('Imagen guardada: ' + ruta)
            count += 1
        else:
            print("Error: No se pudo leer el frame de la cámara")

    sleep(0.1)

Vilib.camera_close()