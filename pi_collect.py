import socket
import struct
import cv2
import csv
import os
import time
from gpiozero import PWMOutputDevice, DigitalOutputDevice
from picamera2 import Picamera2

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
    print("Initializing direct GPU Camera connection...")
    picam2 = Picamera2()
    
    # Force 'viewfinder' mode to use the full 4:3 sensor area to prevent tight cropping
    config = picam2.create_preview_configuration(
        main={"size": (320, 240), "format": "BGR888"},
        transform=None,
        use_case="viewfinder"
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(1.0) 

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', 8486))
    server_socket.listen(1)
    print("Pi Collection Server active. Waiting for laptop controller on port 8486...")

    conn, addr = server_socket.accept()
    print(f"Connected to laptop controller at: {addr}")

    # --- Auto-Resume Frame Counting ---
    existing_frames = [f for f in os.listdir(IMAGES_DIR) if f.startswith('frame_') and f.endswith('.jpg')]
    if existing_frames:
        frame_numbers = [int(f.replace('frame_', '').replace('.jpg', '')) for f in existing_frames]
        frame_count = max(frame_numbers) + 1
        print(f"Found existing data. Resuming collection from frame {frame_count}...")
    else:
        frame_count = 0
        print("No previous data found. Starting fresh from frame 0...")

    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]

    with open(csv_path, 'a', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)

        try:
            while True:
                data = conn.recv(8)
                if len(data) != 8:
                    break

                steering, throttle = struct.unpack(">ff", data)
                drive_hardware(steering, throttle)

                try:
                    frame = picam2.capture_array()
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) # Color fix
                    ret = True
                except Exception as e:
                    print(f"Hardware dropped frame: {e}")
                    ret = False
                
                image_sent = False

                if ret:
                    success, encoded_img = cv2.imencode('.jpg', frame, encode_param)
                    if success:
                        img_bytes = encoded_img.tobytes()
                        
                        conn.sendall(struct.pack(">L", len(img_bytes)) + img_bytes)
                        image_sent = True

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
                    conn.sendall(struct.pack(">L", 0))

        except KeyboardInterrupt:
            print("\nStopping manual data collection session.")
        finally:
            print("Cleaning up resources...")
            drive_hardware(0.0, 0.0) 
            picam2.stop()
            conn.close()
            server_socket.close()

if __name__ == "__main__":
    main()