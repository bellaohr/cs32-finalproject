import socket

HOST = "127.0.0.1"
PORT = 65433

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))

    # receive word length
    data = s.recv(1024).decode()
    if data.startswith("LENGTH"):
        word_length = int(data.split()[1])
        print(f"Guess the {word_length}-letter word!")

    while True:
        guess = input("Enter your guess: ").strip()

        s.sendall(guess.encode())

        response = s.recv(1024).decode()
        print("\nServer says:")
        print(response)
        print()

        if "Correct!" in response:
            break
