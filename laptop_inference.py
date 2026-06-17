import socket
import struct
import cv2
import numpy as np
import tensorflow as tf
import time

# --- Configuration ---
PI_IP_ADDRESS = "10.175.108.173"  # <--- CHANGE THIS TO YOUR PI'S IP ADDRESS
PORT = 8486

def recv_all(sock, count):
    """Ensure we receive exactly the requested number of bytes."""
    buf = b''
    while count:
        newbuf = sock.recv(count)
        if not newbuf: return None
        buf += newbuf
        count -= len(newbuf)
    return buf

def draw_ar_path(frame, steering):
    """
    Draws a curved projected path on the image based on the steering angle.
    """
    height, width = frame.shape[:2]
    
    # 1. Define the Anchor Points
    start_x = width // 2          # Bottom center of the screen
    start_y = height              # Bottom edge
    
    end_y = int(height * 0.4)     # The "horizon" line (40% down from the top)
    
    # Map the -1.0 to 1.0 steering value to physical pixels
    # If steering is 1.0, it shifts the end point 160 pixels right
    max_turn_pixels = width // 2 
    offset_x = int(steering * max_turn_pixels)
    end_x = start_x + offset_x

    # 2. Dynamic Color Coding
    # Green = Straight, Yellow = Slight Turn, Red = Hard Turn
    if abs(steering) < 0.2:
        color = (0, 255, 0)   
    elif abs(steering) < 0.6:
        color = (0, 255, 255) 
    else:
        color = (0, 0, 255)   

    # 3. Calculate the Bezier Curve
    points = []
    # We generate 10 points along the curve to make it smooth
    for t in range(0, 11):
        ratio = t / 10.0
        
        # Quadratic Bezier formula
        # Control point (P1) is placed straight up from the bottom center
        # This forces the curve to start by aiming straight, then smoothly bend
        px = int(((1 - ratio) ** 2) * start_x + 2 * (1 - ratio) * ratio * start_x + (ratio ** 2) * end_x)
        py = int(((1 - ratio) ** 2) * start_y + 2 * (1 - ratio) * ratio * end_y + (ratio ** 2) * end_y)
        points.append((px, py))
        
    pts = np.array(points, np.int32)
    pts = pts.reshape((-1, 1, 2))
    
    # 4. Draw the actual line onto the frame
    cv2.polylines(frame, [pts], isClosed=False, color=color, thickness=5)
    
    # Optional: Draw a target circle at the very end of the path
    cv2.circle(frame, (end_x, end_y), 8, color, -1)
    
    return frame

def main():
    print("Loading Neural Network into RTX 4060 VRAM...")
    model = tf.keras.models.load_model('autodrive_model.keras', safe_mode=False)
    
    # Warm up the GPU (The first prediction is always slow, so we do a dummy run)
    print("Warming up GPU...")
    dummy_image = np.zeros((1, 240, 320, 3), dtype=np.float32)
    model(dummy_image, training=False)

    print(f"Connecting to Pi at {PI_IP_ADDRESS}:{PORT}...")
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # Low latency flag
    client_socket.connect((PI_IP_ADDRESS, PORT))
    print("Link established! AI is taking the wheel.")

    # Kickstart the ping-pong loop by sending a neutral stop command
    client_socket.sendall(struct.pack(">ff", 0.0, 0.0))

    try:
        while True:
            start_time = time.time()

            # 1. Receive the live frame from the Pi
            length_buf = recv_all(client_socket, 4)
            if not length_buf: break
            
            img_size = struct.unpack(">L", length_buf)[0]
            img_data = recv_all(client_socket, img_size)
            if not img_data: break

            # 2. Decode the image bytes
            np_data = np.frombuffer(img_data, dtype=np.uint8)
            raw_frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
            
            # --- THE COLOR ALIGNMENT FIX ---
            # If your video feed looked inverted, it means cv2.imdecode gave us RGB.
            # Let's explicitly define our streams:
            frame_rgb = raw_frame.copy() 
            frame_bgr = cv2.cvtColor(raw_frame, cv2.COLOR_RGB2BGR) # For standard cv2.imshow display

            # 3. Format for the AI Model (Must be true RGB)
            img_batch = np.expand_dims(frame_rgb, axis=0).astype(np.float32)

            # 4. Predict! (Using __call__ for maximum inference speed)
            predictions = model(img_batch, training=False)
            steering = float(predictions[0][0])
            throttle = float(predictions[0][1])

            # Safety override: cap values between mechanical limits
            steering = max(-1.0, min(1.0, steering))
            throttle = max(0.0, min(1.0, throttle))

            # 5. Send driving commands instantly back to the Pi
            client_socket.sendall(struct.pack(">ff", steering, throttle))

            # --- 6. Render the HUD on the correctly formatted BGR Frame ---
            frame_bgr = draw_ar_path(frame_bgr, steering)

            # Calculate and display latency telemetry
            latency_ms = int((time.time() - start_time) * 1000)
            display_text = f"Str: {steering:.2f} | Thr: {throttle:.2f} | Lag: {latency_ms}ms"
            
            height, width = frame_bgr.shape[:2]
            cv2.putText(frame_bgr, display_text, (10, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # This will now display gorgeous, true-to-life colors!
            cv2.imshow("AI Vision", frame_bgr)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("\nEmergency Stop triggered by human.")
    finally:
        client_socket.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()