import time
from vilib import Vilib
from time import sleep
import os

# Start camera

Vilib.camera_start()

# Start display

Vilib.display(local = False, web = True)

# Set path and user name

user_name = os.getlogin()
path = f"/home/{user_name}/picarx-platform"


while True:
    frame = Vilib.img

    if frame is not None:
        if input() == "q":
            break
        if input() == "s":
            _time = time.strftime("%y-%m-%d_%H-%M-%S", time.localtime())
            status = Vilib.take_photo(str(_time),path)

            if status:
                print("Imagen guardada como 'imagen_prueba_vilib'")
            else:
                print("Error: No se pudo guardar la imagen")    
    else:
        print("Error: No se pudo leer el frame de la cámara")
            
    sleep(0.1)   

Vilib.camera_close()