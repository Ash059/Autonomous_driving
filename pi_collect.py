import socket
import struct
import cv2
import csv
import os
import time
from gpiozero import PWMOutputDevice, DigitalOutputDevice

# --- Physical GPIO Pin Mapping (Using BCM Numbering) ---

# --- MOTOR DRIVER 1: FRONT AXLE ---
# Front-Left Motor
FL_PWM = PWMOutputDevice(12)  # Driver 1 ENA
FL_FWD = DigitalOutputDevice(5)   # Driver 1 IN1
FL_REV = DigitalOutputDevice(6)   # Driver 1 IN2

# Front-Right Motor
FR_PWM = PWMOutputDevice(13)  # Driver 1 ENB
FR_FWD = DigitalOutputDevice(23)  # Driver 1 IN3
FR_REV = DigitalOutputDevice(24)  # Driver 1 IN4

# --- MOTOR DRIVER 2: BACK AXLE ---
# Back-Left Motor
BL_PWM = PWMOutputDevice(18)  # Driver 2 ENA
BL_FWD = DigitalOutputDevice(17)  # Driver 2 IN1
BL_REV = DigitalOutputDevice(27)  # Driver 2 IN2

# Back-Right Motor
BR_PWM = PWMOutputDevice(19)  # Driver 2 ENB
BR_FWD = DigitalOutputDevice(22)  # Driver 2 IN3
BR_REV = DigitalOutputDevice(25)  # Driver 2 IN4

# Define Base Speed as a percentage (0.0 to 1.0)
BASE_THROTTLE = 0.6
# --- Setup Dataset Directories ---
DATASET_DIR = "driving_dataset"
IMAGES_DIR = os.path.join(DATASET_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

csv_path = os.path.join(DATASET_DIR, "driving_log.csv")
if not os.path.exists(csv_path):
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["image_path", "steering_angle", "throttle"])

# --- Hardware Configuration Constants ---
BASE_THROTTLE_PWM = 160  
JPEG_QUALITY = 60        

def drive_hardware(steering, throttle_active):
    """
    Translates the steering vector into hardware PWM signals for a dual-driver 4WD setup.
    """
    if not throttle_active:
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

    # Differential Mixing Logic 
    if steering > 0:  # Turning Right
        left_speed = BASE_THROTTLE
        right_speed = BASE_THROTTLE * (1.0 - steering)
    else:             # Turning Left
        right_speed = BASE_THROTTLE
        left_speed = BASE_THROTTLE * (1.0 - abs(steering))

    # Safety clamp: Ensure speeds never exceed 1.0 or drop below 0.0
    left_speed = max(0.0, min(1.0, left_speed))
    right_speed = max(0.0, min(1.0, right_speed))
    print(f"DEBUG: Left={left_speed:.2f}, Right={right_speed:.2f}, Throttle={throttle_active}") # <-- ADD THIS LINE
    # Send the Left speed to both Front-Left and Back-Left motors
    FL_PWM.value = left_speed
    BL_PWM.value = left_speed

    # Send the Right speed to both Front-Right and Back-Right motors
    FR_PWM.value = right_speed
    BR_PWM.value = right_speed

def main():
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    time.sleep(1.0) 

    # Server binds to 0.0.0.0 to listen on all network interfaces
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
                data = conn.recv(5)
                if len(data) != 5:
                    break

                steering, throttle_state = struct.unpack(">fB", data)
                throttle_active = bool(throttle_state)

                drive_hardware(steering, throttle_active)

                if throttle_active:
                    ret, frame = cam.read()
                    if ret:
                        frame_filename = f"frame_{frame_count:06d}.jpg"
                        relative_img_path = os.path.join("images", frame_filename)
                        full_img_path = os.path.join(IMAGES_DIR, frame_filename)

                        cv2.imwrite(full_img_path, frame, encode_param)
                        csv_writer.writerow([relative_img_path, steering, BASE_THROTTLE_PWM])
                        frame_count += 1
                        
                        if frame_count % 100 == 0:
                            print(f"Successfully recorded {frame_count} frames.")

        except KeyboardInterrupt:
            print("\nStopping manual data collection session.")
        finally:
            print("Cleaning up resources...")
            drive_hardware(0.0, False) 
            cam.release()
            conn.close()
            server_socket.close()

if __name__ == "__main__":
    main()