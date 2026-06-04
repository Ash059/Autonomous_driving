import socket
import struct
import pygame
import time
import os
from dotenv import load_dotenv

load_dotenv()

PI_IP_ADDRESS = os.getenv("PI_IP")
PORT = 8486

def main():
    pygame.init()
    pygame.joystick.init()
    
    screen = pygame.display.set_mode((300, 100))
    pygame.display.set_caption("Pi Remote Controller")

    # --- Controller Detection ---
    use_controller = False
    joystick = None
    if pygame.joystick.get_count() > 0:
        joystick = pygame.joystick.Joystick(0)
        joystick.init()
        use_controller = True
        print(f"Controller detected: {joystick.get_name()}")
        print("Using Left Stick for steering and Right Trigger for throttle.")
    else:
        print("No controller found. Falling back to Keyboard smoothing mode.")

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"Connecting to Pi at {PI_IP_ADDRESS}:{PORT}...")
    try:
        client_socket.connect((PI_IP_ADDRESS, PORT))
        print("Network connection established successfully.")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    running = True
    clock = pygame.time.Clock()
    
    # Keyboard Smoothing Variables
    current_steering = 0.0
    turn_speed = 1.5   
    return_speed = 3.0 
    steering_left = False
    steering_right = False

    while running:
        dt = clock.tick(30) / 1000.0  
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            # Only track keyboard events if we aren't using a controller
            if not use_controller:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_LEFT, pygame.K_a): steering_left = True
                    elif event.key in (pygame.K_RIGHT, pygame.K_d): steering_right = True
                elif event.type == pygame.KEYUP:
                    if event.key in (pygame.K_LEFT, pygame.K_a): steering_left = False
                    elif event.key in (pygame.K_RIGHT, pygame.K_d): steering_right = False

        final_steering = 0.0
        final_throttle = 0.0

        if use_controller:
            # Axis 0 is usually Left Stick X-Axis (-1.0 to 1.0)
            final_steering = joystick.get_axis(0)
            if abs(final_steering) < 0.08: # Hall effect deadzone
                final_steering = 0.0

            # Axis 5 is usually Right Trigger in Pygame (Rests at -1.0, Fully Pressed is 1.0)
            trigger_val = joystick.get_axis(5)
            # Map the -1.0 to 1.0 range into a clean 0.0 to 1.0 percentage
            final_throttle = (trigger_val + 1.0) / 2.0 
            if final_throttle < 0.05: 
                final_throttle = 0.0
                
        else:
            # Fallback Keyboard Logic
            keys = pygame.key.get_pressed()
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                final_throttle = 0.6  # Fixed speed for keyboard
                
            if steering_left:
                current_steering -= turn_speed * dt
                if current_steering < -1.0: current_steering = -1.0
            elif steering_right:
                current_steering += turn_speed * dt
                if current_steering > 1.0: current_steering = 1.0
            else:
                if current_steering > 0:
                    current_steering -= return_speed * dt
                    if current_steering < 0: current_steering = 0.0
                elif current_steering < 0:
                    current_steering += return_speed * dt
                    if current_steering > 0: current_steering = 0.0
                    
            final_steering = current_steering

        # Pack BOTH values as continuous Floats (8 bytes total) -> ">ff"
        packet = struct.pack(">ff", final_steering, final_throttle)
        
        try:
            client_socket.sendall(packet)
        except Exception as e:
            print(f"Transmission lost: {e}")
            break

    pygame.quit()
    client_socket.close()

if __name__ == "__main__":
    main()