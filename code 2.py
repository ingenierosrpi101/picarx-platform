import cv2
import numpy as np
import imutils
import os
Datos = 'n'
if not os.path.exists(Datos):
    print('Carpeta creada: ',Datos)
    os.makedirs(Datos)
cap = cv2.VideoCapture(1,cv2.CAP_DSHOW)
count = 0
while True:
    ret, frame = cap.read()
    if ret == False: break
    k = cv2.waitKey(1)
    if k == ord('s'):
        cv2.imwrite(Datos+'/objeto_{}.jpg'.format(count),frame)
        print('Imagen guardada:'+'/objeto_{}.jpg'.format(count))
        count = count +1
    if k == 27:
        break
    cv2.imshow('frame',frame)

cap.release()
cv2.destroyAllWindows()
