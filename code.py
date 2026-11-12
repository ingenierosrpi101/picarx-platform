import cv2
import os
from vilib import Vilib

Datos = 'p'
x1, y1 = 190, 80
x2, y2 = 450, 398
FUENTE = cv2.FONT_HERSHEY_SIMPLEX

if not os.path.exists(Datos):
    print('Carpeta creada: ', Datos)
    os.makedirs(Datos)

count = 0

try:
    Vilib.camera_start()
    Vilib.display(local=False, web=True)

    while True:
        frame_vilib = Vilib.img

        if frame_vilib is None:
            # Aunque no haya imagen, atender teclado y ventanas
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                break
            continue

        # Copia limpia (para guardar) y copia con dibujos (para mostrar)
        imAux = frame_vilib.copy()
        frame = frame_vilib.copy()

        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
        cv2.putText(frame, f"Guardadas: {count}  |  s: guardar  q/Esc: salir",
                    (10, 25), FUENTE, 0.6, (0, 255, 0), 2, cv2.LINE_AA)

        cv2.imshow('frame', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            objeto = imAux[y1:y2, x1:x2]
            ruta = Datos + '/objeto_{}.jpg'.format(count)
            cv2.imwrite(ruta, objeto)
            print('Imagen guardada: ' + ruta)
            count += 1
        elif key == ord('q') or key == 27:
            break

finally:
    try:
        cv2.destroyAllWindows()
    finally:
        Vilib.camera_close()