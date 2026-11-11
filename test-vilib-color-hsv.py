import cv2
from vilib import Vilib
import argparse
import os
#cambiar a path 
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Start Camera

Vilib.camera_start()

# Start display

Vilib.display(local = False, web = True)

user_name = os.getlogin()
path = f"/home/{user_name}/picarx-platform"

max_value = 255
max_value_H = 360//2
low_H = 0
low_S = 0
low_V = 0
high_H = max_value_H
high_S = max_value
high_V = max_value
window_capture_name = 'Video Capture'
window_detection_name = 'Object Detection'
low_H_name = 'Low H'
low_S_name = 'Low S'
low_V_name = 'Low V'
high_H_name = 'High H'
high_S_name = 'High S'
high_V_name = 'High V'

## [low]
def on_low_H_thresh_trackbar(val):
    global low_H
    global high_H
    low_H = val
    low_H = min(high_H-1, low_H)
    cv2.setTrackbarPos(low_H_name, window_detection_name, low_H)
## [low]

## [high]
def on_high_H_thresh_trackbar(val):
    global low_H
    global high_H
    high_H = val
    high_H = max(high_H, low_H+1)
    cv2.setTrackbarPos(high_H_name, window_detection_name, high_H)
## [high]

def on_low_S_thresh_trackbar(val):
    global low_S
    global high_S
    low_S = val
    low_S = min(high_S-1, low_S)
    cv2.setTrackbarPos(low_S_name, window_detection_name, low_S)

def on_high_S_thresh_trackbar(val):
    global low_S
    global high_S
    high_S = val
    high_S = max(high_S, low_S+1)
    cv2.setTrackbarPos(high_S_name, window_detection_name, high_S)

def on_low_V_thresh_trackbar(val):
    global low_V
    global high_V
    low_V = val
    low_V = min(high_V-1, low_V)
    cv2.setTrackbarPos(low_V_name, window_detection_name, low_V)

def on_high_V_thresh_trackbar(val):
    global low_V
    global high_V
    high_V = val
    high_V = max(high_V, low_V+1)
    cv2.setTrackbarPos(high_V_name, window_detection_name, high_V)

## [cap]
#cap = cv2.VideoCapture(0)
## [cap]



## [window]
cv2.namedWindow(window_capture_name)
cv2.namedWindow(window_detection_name)
## [window]

## [trackbar]
cv2.createTrackbar(low_H_name, window_detection_name , low_H, max_value_H, on_low_H_thresh_trackbar)
cv2.createTrackbar(high_H_name, window_detection_name , high_H, max_value_H, on_high_H_thresh_trackbar)
cv2.createTrackbar(low_S_name, window_detection_name , low_S, max_value, on_low_S_thresh_trackbar)
cv2.createTrackbar(high_S_name, window_detection_name , high_S, max_value, on_high_S_thresh_trackbar)
cv2.createTrackbar(low_V_name, window_detection_name , low_V, max_value, on_low_V_thresh_trackbar)
cv2.createTrackbar(high_V_name, window_detection_name , high_V, max_value, on_high_V_thresh_trackbar)
## [trackbar]

while True:

    frame_vilib = Vilib.img

    if frame_vilib is None:
        continue

    frame = frame_vilib.copy()

    height, width = frame.shape[:2]

    # Definir la región de interés (ROI)
    x1 = int(width * 0.15)
    x2 = int(width * 0.85)

    y1 = int(height * 0.65)
    y2 = int(height * 0.85)

    roi = frame[y1:y2, x1:x2]

    # Procesar la ROI mediante HSV
    frame_HSV = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    frame_threshold = cv2.inRange(
        frame_HSV,
        (low_H, low_S, low_V),
        (high_H, high_S, high_V)
    )

    # Detectar contornos
    contornos, _ = cv2.findContours(
        frame_threshold,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    for c in contornos:

        area = cv2.contourArea(c)

        if area > 3000:

            M = cv2.moments(c)

            if M["m00"] == 0:
                continue

            # Coordenadas del centroide en la imagen original
            x = int(M["m10"] / M["m00"]) + x1
            y = int(M["m01"] / M["m00"]) + y1

            cv2.circle(frame, (x, y), 7, (0, 255, 0), -1)

            font = cv2.FONT_HERSHEY_SIMPLEX

            cv2.putText(
                frame,
                f"{x},{y}",
                (x + 10, y),
                font,
                0.75,
                (0, 255, 0),
                1,
                cv2.LINE_AA
            )

            # Dibujar contorno en coordenadas originales
            nuevoContorno = cv2.convexHull(c)

            nuevoContorno[:, :, 0] += x1
            nuevoContorno[:, :, 1] += y1

            cv2.drawContours(
                frame,
                [nuevoContorno],
                0,
                (255, 0, 0),
                3
            )

    # Dibujar los límites de la ROI
    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        (0, 255, 255),
        2
    )

    # Mostrar resultados
    cv2.imshow(window_capture_name, frame)
    cv2.imshow(window_detection_name, frame_threshold)

    key = cv2.waitKey(30) & 0xFF

    if key == ord('q') or key == 27:
        break

cv2.destroyAllWindows()
Vilib.camera_close()


