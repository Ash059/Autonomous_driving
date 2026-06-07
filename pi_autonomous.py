import socket
import struct
import cv2
import time
from gpiozero import PWMOutputDevice, DigitalOutputDevice
from picamera2 import Picamera2

# --- Physical GPIO Pin Mapping ---
FL_PWM = PWMOutputDevice(12); FL_FWD = DigitalOutputDevice(5);  FL_REV = DigitalOutputDevice(6)   
FR_PWM = PWMOutputDevice(13); FR_FWD = DigitalOutputDevice(23); FR_REV = DigitalOutputDevice(24)  
BL_PWM = PWMOutputDevice(18); BL_FWD = DigitalOutputDevice(17); BL_REV = DigitalOutputDevice(27)  
BR_PWM = PWMOutputDevice(19); BR_FWD = DigitalOutputDevice(22); BR_REV = DigitalOutputDevice(25)  

JPEG_QUALITY = 50 # Lower quality = smaller file = faster Wi-Fi transmission

def drive_hardware(steering, throttle):
    if throttle <= 0.05: # Slight deadzone to ensure it stops
        FL_PWM.value, FR_PWM.value, BL_PWM.value, BR_PWM.value = 0.0, 0.0, 0.0, 0.0
        FL_FWD.off(); FL_REV.off(); FR_FWD.off(); FR_REV.off()
        BL_FWD.off(); BL_REV.off(); BR_FWD.off(); BR_REV.off()
        return

    FL_FWD.on(); FL_REV.off(); FR_FWD.on(); FR_REV.off()
    BL_FWD.on(); BL_REV.off(); BR_FWD.on(); BR_REV.off()

    if steering > 0:  
        left_speed = throttle
        right_speed = throttle * (1.0 - steering)
    else:             
        right_speed = throttle
        left_speed = throttle * (1.0 - abs(steering))

    FL_PWM.value = max(0.0, min(1.0, left_speed))
    BL_PWM.value = max(0.0, min(1.0, left_speed))
    FR_PWM.value = max(0.0, min(1.0, right_speed))
    BR_PWM.value = max(0.0, min(1.0, right_speed))

def main():
    print("Initializing Camera...")
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": (320, 240), "format": "BGR888"},
        use_case="viewfinder"
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(1.0)

    # --- Network Setup ---
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # Low latency flag
    server_socket.bind(('0.0.0.0', 8486))
    server_socket.listen(1)
    
    print("Autonomous Mode Active. Waiting for AI Laptop on port 8486...")
    conn, addr = server_socket.accept()
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    print(f"Brain connected from: {addr}")

    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]

    try:
        while True:
            # 1. Wait for the AI's command
            data = conn.recv(8)
            if len(data) != 8: break
            
            steering, throttle = struct.unpack(">ff", data)
            drive_hardware(steering, throttle)

            # 2. Grab the next frame and send it to the AI
            frame = picam2.capture_array()
            # BGR format natively from Picamera2 config
            success, encoded_img = cv2.imencode('.jpg', frame, encode_param)
            
            if success:
                img_bytes = encoded_img.tobytes()
                conn.sendall(struct.pack(">L", len(img_bytes)) + img_bytes)

    except Exception as e:
        print(f"Connection lost: {e}")
    finally:
        print("Shutting down motors and camera.")
        drive_hardware(0.0, 0.0)
        picam2.stop()
        conn.close()
        server_socket.close()

if __name__ == "__main__":
    main()