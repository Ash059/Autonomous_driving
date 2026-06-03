import socket
import struct
import pygame
import time
import os
from dotenv import load_dotenv

# Load IP addresses from the hidden .env file
load_dotenv()

# --- Network Target Configuration ---
PI_IP_ADDRESS = os.getenv("PI_IP")
PORT = 8486

def main():
    # Initialize Pygame window to capture keyboard focus
    pygame.init()
    screen = pygame.display.set_mode((300, 100))
    pygame.display.set_caption("Pi Remote Controller")

    # Set up the network socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"Connecting to Pi at {PI_IP_ADDRESS}:{PORT}...")
    try:
        client_socket.connect((PI_IP_ADDRESS, PORT))
        print("Connected! Keep this window focused and use Arrow Keys or WASD to drive.")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    running = True
    clock = pygame.time.Clock()
    
    # --- Steering Smoothing Variables ---
    current_steering = 0.0
    turn_speed = 1.5   
    return_speed = 3.0 

    # --- Absolute State Trackers (Fixes Keyboard Ghosting) ---
    throttle_active = 0
    steering_left = False
    steering_right = False

    while running:
        # Get delta time (dt) in seconds
        dt = clock.tick(30) / 1000.0  
        
        # 1. Catch absolute KEYDOWN and KEYUP events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    throttle_active = 1
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    steering_left = True
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    steering_right = True
                    
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_UP, pygame.K_w):
                    throttle_active = 0
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    steering_left = False
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    steering_right = False

        # 2. Apply smoothed math based on locked states
        if steering_left:
            current_steering -= turn_speed * dt
            if current_steering < -1.0: 
                current_steering = -1.0
                
        elif steering_right:
            current_steering += turn_speed * dt
            if current_steering > 1.0: 
                current_steering = 1.0
                
        else:
            if current_steering > 0:
                current_steering -= return_speed * dt
                if current_steering < 0: 
                    current_steering = 0.0
            elif current_steering < 0:
                current_steering += return_speed * dt
                if current_steering > 0: 
                    current_steering = 0.0

        # Pack the data (Float for steering, Unsigned Char for throttle)
        packet = struct.pack(">fB", current_steering, throttle_active)
        
        try:
            client_socket.sendall(packet)
        except Exception as e:
            print(f"Transmission lost: {e}")
            break

    pygame.quit()
    client_socket.close()

if __name__ == "__main__":
    main()