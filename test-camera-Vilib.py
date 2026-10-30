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
        # Frame is a NumPy / OpenCV image
        print(frame.shape)

    sleep(0.1)    