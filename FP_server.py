import socket
import random

HOST = "127.0.0.1"
PORT = 65433

WORDS = ["cats", "dogs", "plane", "train", "brick", "apple", "grape"]

def compare_words(secret, guess, current_state):
    revealed = list(current_state)
    correct_spot = 0
    wrong_spot = 0

    secret_used = [False] * len(secret)
    guess_used = [False] * len(guess)

    # First pass: correct spot
    for i in range(len(secret)):
        if guess[i] == secret[i]:
            revealed[i] = guess[i]
            correct_spot += 1
            secret_used[i] = True
            guess_used[i] = True

    # Second pass: correct letter, wrong spot
    for i in range(len(guess)):
        if guess_used[i]:
            continue
        for j in range(len(secret)):
            if not secret_used[j] and guess[i] == secret[j]:
                wrong_spot += 1
                secret_used[j] = True
                break

    return "".join(revealed), correct_spot, wrong_spot


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()

    print("Server started. Waiting for connection...")

    conn, addr = s.accept()
    with conn:
        print(f"Connected by {addr}")

        secret = random.choice(WORDS)
        word_length = len(secret)

        # initial hidden word
        current_state = "*" * word_length

        # send length to client
        conn.sendall(f"LENGTH {word_length}".encode())

        while True:
            data = conn.recv(1024)
            if not data:
                break

            guess = data.decode().strip().lower()

            # validation
            if len(guess) != word_length or not guess.isalpha():
                conn.sendall(f"Invalid guess. Enter a {word_length}-letter word.".encode())
                continue

            current_state, correct, wrong = compare_words(secret, guess, current_state)

            if guess == secret:
                conn.sendall(f"Correct! The word was '{secret}'".encode())
                break
            else:
                message = (
                    f"Word: {current_state}\n"
                    f"{correct} correct position\n"
                    f"{wrong} wrong position"
                )
                conn.sendall(message.encode())

        print("Game over.")
