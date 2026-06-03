import socket
import struct
import cv2
import time
import os
from dotenv import load_dotenv

load_dotenv()

# --- Configuration Constants ---
LAPTOP_IP_ADDRESS = os.getenv("LAPTOP_IP")
PORT = 8485
FRAME_WIDTH = 320
FRAME_HEIGHT = 240
JPEG_QUALITY = 60 

def hardware_control(steering, brake):
    """
    Interface directly with your hardware motor drivers here.
    """
    if brake > 0.5:
        pass
    else:
        throttle = 150 
        if steering > 0:
            left_pwm = throttle
            right_pwm = int(throttle * (1.0 - steering))
        else:
            right_pwm = throttle
            left_pwm = int(throttle * (1.0 - abs(steering)))
            
        pass

def main():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    print(f"Attempting connection to inference server at {LAPTOP_IP_ADDRESS}:{PORT}...")
    try:
        client_socket.connect((LAPTOP_IP_ADDRESS, PORT))
        print("Network connection established successfully.")
    except Exception as e:
        print(f"Failed to connect to server: {e}")
        return

    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    time.sleep(1.0) 

    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]

    try:
        while True:
            start_time = time.time()
            
            ret, frame = cam.read()
            if not ret:
                break
            
            success, encoded_img = cv2.imencode('.jpg', frame, encode_param)
            if not success:
                continue
                
            img_bytes = encoded_img.tobytes()
            payload_size = len(img_bytes)

            client_socket.sendall(struct.pack(">L", payload_size) + img_bytes)

            response_header = client_socket.recv(8)
            if len(response_header) != 8:
                break

            steering, brake = struct.unpack(">ff", response_header)

            hardware_control(steering, brake)
            
    except KeyboardInterrupt:
        print("\nManual termination caught.")
    finally:
        print("Releasing hardware assets and connections...")
        cam.release()
        client_socket.close()

if __name__ == "__main__":
    main()