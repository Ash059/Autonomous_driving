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
    # Initialize a minimalist Pygame window to capture keyboard focus
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
    turn_speed = 1.5   # How fast the wheels turn to the side (units per second)
    return_speed = 3.0 # How fast the wheels snap back to center (units per second)

    while running:
        # Get delta time (dt) in seconds (e.g., ~0.033 seconds for 30fps)
        dt = clock.tick(30) / 1000.0  
        
        # Check if the user closed the window
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Read the current hardware array of all keys pressed
        keys = pygame.key.get_pressed()

        # --- Throttle Logic (Binary) ---
        throttle_active = 0
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            throttle_active = 1

        # --- Smoothed Steering Logic (Continuous Float) ---
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            # Ramp towards -1.0
            current_steering -= turn_speed * dt
            if current_steering < -1.0: 
                current_steering = -1.0
                
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            # Ramp towards 1.0
            current_steering += turn_speed * dt
            if current_steering > 1.0: 
                current_steering = 1.0
                
        else:
            # No keys pressed: auto-center the wheels mathematically
            if current_steering > 0:
                current_steering -= return_speed * dt
                if current_steering < 0: 
                    current_steering = 0.0
            elif current_steering < 0:
                current_steering += return_speed * dt
                if current_steering > 0: 
                    current_steering = 0.0

        # Pack the continuously changing float value and the binary throttle state
        # ">fB" means: Big-Endian, 1 Float (4 bytes), 1 Unsigned Char (1 byte)
        packet = struct.pack(">fB", current_steering, throttle_active)
        
        try:
            # Push to the Raspberry Pi over Wi-Fi
            client_socket.sendall(packet)
        except Exception as e:
            print(f"Transmission lost: {e}")
            break

    # Clean up on exit
    pygame.quit()
    client_socket.close()

if __name__ == "__main__":
    main()