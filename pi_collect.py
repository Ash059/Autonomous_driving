import socket
import struct
import cv2
import csv
import os
import time

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
    Apply your differential drive equations to your physical GPIO pins.
    """
    if not throttle_active:
        left_pwm = 0
        right_pwm = 0
    else:
        if steering > 0:  # Turning Right
            left_pwm = BASE_THROTTLE_PWM
            right_pwm = int(BASE_THROTTLE_PWM * (1.0 - steering))
        else:             # Turning Left
            right_pwm = BASE_THROTTLE_PWM
            left_pwm = int(BASE_THROTTLE_PWM * (1.0 - abs(steering)))

    # Insert your specific hardware GPIO/PWM write statements here
    pass

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