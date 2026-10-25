from picarx import Picarx
import time

if __name__ == "_main__":
    try:
        px = Picarx()

        # Move forward
        px.forward(30)
        time.sleep(2)

        # Move backward
        px.backward(30)
        time.sleep(2)

        # Turn left
        
