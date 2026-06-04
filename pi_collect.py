import socket
import struct
import cv2
import csv
import os
import time
from gpiozero import PWMOutputDevice, DigitalOutputDevice

DATASET_DIR = "driving_dataset"
IMAGES_DIR = os.path.join(DATASET_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

csv_path = os.path.join(DATASET_DIR, "driving_log.csv")
if not os.path.exists(csv_path):
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["image_path", "steering_angle", "throttle"])

# --- Physical GPIO Pin Mapping (Dual L298N Drivers) ---
FL_PWM = PWMOutputDevice(12) 
FL_FWD = DigitalOutputDevice(5)   
FL_REV = DigitalOutputDevice(6)   
FR_PWM = PWMOutputDevice(13)  
FR_FWD = DigitalOutputDevice(23)  
FR_REV = DigitalOutputDevice(24)  

BL_PWM = PWMOutputDevice(18)  
BL_FWD = DigitalOutputDevice(17)  
BL_REV = DigitalOutputDevice(27)  
BR_PWM = PWMOutputDevice(19)  
BR_FWD = DigitalOutputDevice(22)  
BR_REV = DigitalOutputDevice(25)  

JPEG_QUALITY = 60        

def drive_hardware(steering, throttle):
    """
    Translates the steering vector and analog throttle into hardware PWM signals.
    """
    if throttle == 0.0:
        FL_PWM.value, FR_PWM.value = 0.0, 0.0
        BL_PWM.value, BR_PWM.value = 0.0, 0.0
        FL_FWD.off(); FL_REV.off()
        FR_FWD.off(); FR_REV.off()
        BL_FWD.off(); BL_REV.off()
        BR_FWD.off(); BR_REV.off()
        return

    FL_FWD.on(); FL_REV.off()
    FR_FWD.on(); FR_REV.off()
    BL_FWD.on(); BL_REV.off()
    BR_FWD.on(); BR_REV.off()

    # The throttle now dictates the base speed dynamically
    if steering > 0:  
        left_speed = throttle
        right_speed = throttle * (1.0 - steering)
    else:             
        right_speed = throttle
        left_speed = throttle * (1.0 - abs(steering))

    left_speed = max(0.0, min(1.0, left_speed))
    right_speed = max(0.0, min(1.0, right_speed))

    FL_PWM.value = left_speed
    BL_PWM.value = left_speed
    FR_PWM.value = right_speed
    BR_PWM.value = right_speed

def main():
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    time.sleep(1.0) 

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', 8486))
    server_socket.listen(1)
    print("Pi Collection Server active. Waiting for laptop controller on port 8486...")

    conn, addr = server_socket.accept()
    print(f"Connected to laptop controller at: {addr}")

    frame_count = 0
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]

    with open(csv_path, 'a', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)

        try:
            while True:
                # We now expect 8 bytes (Two floats) instead of 5
                data = conn.recv(8)
                if len(data) != 8:
                    break

                # Unpack the two floats
                steering, throttle = struct.unpack(">ff", data)

                drive_hardware(steering, throttle)

                if throttle > 0.0:
                    ret, frame = cam.read()
                    if ret:
                        frame_filename = f"frame_{frame_count:06d}.jpg"
                        relative_img_path = os.path.join("images", frame_filename)
                        full_img_path = os.path.join(IMAGES_DIR, frame_filename)

                        cv2.imwrite(full_img_path, frame, encode_param)
                        # Log the exact variable throttle position used
                        csv_writer.writerow([relative_img_path, steering, throttle])
                        frame_count += 1
                        
                        if frame_count % 100 == 0:
                            print(f"Successfully recorded {frame_count} frames.")

        except KeyboardInterrupt:
            print("\nStopping manual data collection session.")
        finally:
            print("Cleaning up resources...")
            drive_hardware(0.0, 0.0) 
            cam.release()
            conn.close()
            server_socket.close()

if __name__ == "__main__":
    main()