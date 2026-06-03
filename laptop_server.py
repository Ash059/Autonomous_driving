import socket
import struct
import cv2
import torch
import torch.nn as nn
import numpy as np

class PilotNet(nn.Module):
    def __init__(self):
        super(PilotNet, self).__init__()
        self.conv_layers = nn.Sequential(
            nn.Conv2d(3, 24, kernel_size=5, stride=2),
            nn.ELU(),
            nn.Conv2d(24, 36, kernel_size=5, stride=2),
            nn.ELU(),
            nn.Conv2d(36, 48, kernel_size=5, stride=2),
            nn.ELU(),
            nn.Conv2d(48, 64, kernel_size=3, stride=1),
            nn.ELU(),
            nn.Conv2d(64, 64, kernel_size=3, stride=1),
            nn.ELU()
        )
        self.linear_layers = nn.Sequential(
            nn.Linear(1152, 100),
            nn.ELU(),
            nn.Linear(100, 50),
            nn.ELU(),
            nn.Linear(50, 10),
            nn.ELU(),
            nn.Linear(10, 1) 
        )

    def forward(self, x):
        x = self.conv_layers(x)
        x = x.view(x.size(0), -1)
        x = self.linear_layers(x)
        return x

def recv_all(sock, num_bytes):
    buffer = b""
    while len(buffer) < num_bytes:
        packet = sock.recv(num_bytes - len(buffer))
        if not packet:
            return None
        buffer += packet
    return buffer

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    model = PilotNet().to(device)
    model.eval() 

    # Server binds to 0.0.0.0 to listen on all network interfaces
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', 8485)) 
    server_socket.listen(1)
    print("Inference Server active. Waiting for Raspberry Pi connection on port 8485...")

    conn, addr = server_socket.accept()
    print(f"Connected to vehicle client at: {addr}")

    try:
        while True:
            header = recv_all(conn, 4)
            if not header:
                break
            msg_size = struct.unpack(">L", header)[0]

            frame_bytes = recv_all(conn, msg_size)
            if not frame_bytes:
                break

            np_data = np.frombuffer(frame_bytes, dtype=np.uint8)
            frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)

            # Preprocessing
            h, w, _ = frame.shape
            cropped = frame[int(h*0.4):h, 0:w]
            resized = cv2.resize(cropped, (200, 66))
            
            input_tensor = torch.from_numpy(resized).float().permute(2, 0, 1) / 255.0
            input_tensor = input_tensor.unsqueeze(0).to(device)

            # Prediction
            with torch.no_grad():
                steering_output = model(input_tensor)
                steering = steering_output.item() 

            brake = 0.0 
            
            response_payload = struct.pack(">ff", steering, brake)
            conn.sendall(response_payload)

    except Exception as e:
        print(f"Pipeline error encountered: {e}")
    finally:
        print("Closing network connections...")
        conn.close()
        server_socket.close()

if __name__ == "__main__":
    main()