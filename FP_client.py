import socket

HOST = "127.0.0.1"
PORT = 65434

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))

    while True:
        data = s.recv(1024)
        if not data:
            break

        message = data.decode()
        print(message, end="")

        # server prompting input
        if message.startswith("INPUT:"):
            user_input = input()
            s.sendall(user_input.encode())
