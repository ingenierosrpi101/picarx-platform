import cv2
import numpy as np
from vilib import Vilib
from time import sleep

# Start camera

Vilib.camera_start()

# Start display

Vilib.display(local = False, web = True)

while True:
    frame = Vilib.img

    if frame is not None:
        if input() == "q":
            break
        if input() == "s":
            cv2.imwrite("imagen_prueba_vilib.jpg", frame)
            print("Imagen guardada como 'imagen_prueba_vilib'")    
    else:
        print("Error: No se pudo leer el frame de la cámara")
            
    sleep(0.1)   

Vilib.camera_close()