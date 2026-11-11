# Librerias

import time
import cv2
from vilib import Vilib
from picarx import Picarx
import readchar

estado = "Parado"
manual = '''

Presiona teclas para controlar el carro:

    w = AVANCE
    s = ALTO_10S
    a = ESPERA_PEATON
    d = PARO_SEGURO
    q = Salir del programa

'''

def show_manual():
    print(manual)

if __name__ == "__main__":
    try:
        px = Picarx()
        show_manual()
        alto_habilitado = True
        inicio_sin_alto = None
        while True:
            key = cv2.waitKey(1) & 0xFF

            # Primero: atender las teclas.
            if key == ord("q"):
                break

            elif key == ord("d"):
                px.stop()
                estado = "PARO_SEGURO"
                inicio_alto = None

            elif key == ord("w") and estado in ("Parado", "PARO_SEGURO"):
                estado = "AVANCE"
                px.forward(20)

            elif key == ord("s") and estado == "AVANCE" and alto_habilitado:
                px.stop()
                inicio_alto = time.monotonic()
                alto_habilitado = False
                estado = "ALTO_10S"

        # Después: revisar el temporizador en CADA vuelta.
            if estado == "ALTO_10S":
                if time.monotonic() - inicio_alto >= 10:
                    estado = "AVANCE"
                    inicio_alto = None
                    px.forward(20)
            
    finally:   
        print("Saliendo del programa...")
        px.stop()
        px.reset()
        cv2.destroyAllWindows()                