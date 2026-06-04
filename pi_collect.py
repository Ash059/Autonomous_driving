import socket
import struct
import cv2
import csv
import os
import time
from gpiozero import PWMOutputDevice, DigitalOutputDevice

# --- Setup Dataset Directories ---
DATASET_DIR = "driving_dataset"
IMAGES_DIR = os.path.join(DATASET_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

csv_path = os.path.join(DATASET_DIR, "driving_log.csv")
if not os.path.exists(csv_path):
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["image_path", "steering_angle", "throttle"])

# --- Physical GPIO Pin Mapping (Dual L298N Drivers) ---

# MOTOR DRIVER 1: FRONT AXLE
FL_PWM = PWMOutputDevice(12)  
FL_FWD = DigitalOutputDevice(5)   
FL_REV = DigitalOutputDevice(6)   

FR_PWM = PWMOutputDevice(13)  
FR_FWD = DigitalOutputDevice(23)  
FR_REV = DigitalOutputDevice(24)  

# MOTOR DRIVER 2: BACK AXLE
BL_PWM = PWMOutputDevice(18)  
BL_FWD = DigitalOutputDevice(17)  
BL_REV = DigitalOutputDevice(27)  

BR_PWM = PWMOutputDevice(19)  
BR_FWD = DigitalOutputDevice(22)  
BR_REV = DigitalOutputDevice(25)  

# --- Hardware Configuration Constants ---
JPEG_QUALITY = 60        

def drive_hardware(steering, throttle):
    """
    Translates the steering vector and analog throttle into hardware PWM signals.
    """
    if throttle == 0.0:
        # Stop all motors
        FL_PWM.value, FR_PWM.value = 0.0, 0.0
        BL_PWM.value, BR_PWM.value = 0.0, 0.0
        FL_FWD.off(); FL_REV.off()
        FR_FWD.off(); FR_REV.off()
        BL_FWD.off(); BL_REV.off()
        BR_FWD.off(); BR_REV.off()
        return

    # Set all 4 wheels to drive forward direction
    FL_FWD.on(); FL_REV.off()
    FR_FWD.on(); FR_REV.off()
    BL_FWD.on(); BL_REV.off()
    BR_FWD.on(); BR_REV.off()

    # The throttle now dictates the base speed dynamically
    if steering > 0:  # Turning Right
        left_speed = throttle
        right_speed = throttle * (1.0 - steering)
    else:             # Turning Left
        right_speed = throttle
        left_speed = throttle * (1.0 - abs(steering))

    # Safety clamp: Ensure speeds never exceed 1.0 or drop below 0.0
    left_speed = max(0.0, min(1.0, left_speed))
    right_speed = max(0.0, min(1.0, right_speed))

    FL_PWM.value = left_speed
    BL_PWM.value = left_speed
    FR_PWM.value = right_speed
    BR_PWM.value = right_speed

def main():
    # If index 0 throws the V4L2 error again, change this back to 1
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    time.sleep(1.0) 
    if not cam.isOpened():
        print("CRITICAL ERROR: Camera failed to initialize! Check wiring or index.")
        exit()

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
                # We expect 8 bytes (Two floats)
                data = conn.recv(8)
                if len(data) != 8:
                    break

                # Unpack the two floats
                steering, throttle = struct.unpack(">ff", data)

                drive_hardware(steering, throttle)

                # Always read camera to provide a live feed to the laptop
                ret, frame = cam.read()
                image_sent = False
                
                if ret:
                    # Compress the frame to save Wi-Fi bandwidth
                    success, encoded_img = cv2.imencode('.jpg', frame, encode_param)
                    if success:
                        img_bytes = encoded_img.tobytes()
                        
                        # Send the live frame back to the laptop
                        conn.sendall(struct.pack(">L", len(img_bytes)) + img_bytes)
                        image_sent = True

                        # ONLY save to the dataset if you are pressing the gas trigger
                        if throttle > 0.0:
                            frame_filename = f"frame_{frame_count:06d}.jpg"
                            relative_img_path = os.path.join("images", frame_filename)
                            full_img_path = os.path.join(IMAGES_DIR, frame_filename)

                            with open(full_img_path, 'wb') as f:
                                f.write(img_bytes)
                                
                            csv_writer.writerow([relative_img_path, steering, throttle])
                            frame_count += 1
                            
                            if frame_count % 100 == 0:
                                print(f"Successfully recorded {frame_count} frames.")
                                
                if not image_sent:
                    # FAIL-SAFE: If camera dropped a frame, send a 0-byte header so laptop doesn't freeze
                    conn.sendall(struct.pack(">L", 0))
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