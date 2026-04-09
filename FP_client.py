import socket

HOST = "127.0.0.1"
PORT = 65432

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))

    while True:
        data = s.recv(1024)
        if not data:
            break

        message = data.decode()
        print(message, end="")

        # If server is prompting input
        if "Enter" in message:
            user_input = input()
            s.sendall(user_input.encode())
