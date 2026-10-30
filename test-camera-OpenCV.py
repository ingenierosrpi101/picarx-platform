import cv2
from picamera2 import Picamera2

#camera = cv2.VideoCapture(0)

picam2 = Picamera2()
picam2.configure(picam2.create_still_configuration(main={"size": (640, 480)}))
picam2.start()

if not picam2:
    print("Camera not available")
    exit()

try:
    while True:
        frame = picam2.capture_array()
        cv2.imshow("Camera", frame)

        print("Presiona 's' para guardar la imagen o 'q' para salir del programa.")

        key = cv2.waitKey(1) & 0xFF 

        if key == ord("s"):
            cv2.imwrite("imagen_prueba", frame)
            print("Imagen guardada como 'imagen_prueba'")

        if key == ord("q"):
            break
finally:
    picam2.stop()
    cv2.destroyAllWindows()
 