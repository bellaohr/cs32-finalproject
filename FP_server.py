import socket

HOST = "127.0.0.1"
PORT = 65434


def compare_words(secret, guess, current_state):
    revealed = list(current_state)
    correct_spot = 0
    wrong_spot = 0

    secret_used = [False] * len(secret)
    guess_used = [False] * len(guess)

    # is it in the right position
    for i in range(len(secret)):
        if guess[i] == secret[i]:
            revealed[i] = guess[i]
            correct_spot += 1
            secret_used[i] = True
            guess_used[i] = True

    # right letter, wrong position
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

    print("Server started. Waiting for 2 players...")

    conn1, addr1 = s.accept()
    print("Player 1 connected:", addr1)
    conn1.sendall(b"You are Player 1 (word setter).\nEnter a 4 to 6 letter word:")

    conn2, addr2 = s.accept()
    print("Player 2 connected:", addr2)
    conn2.sendall(b"You are Player 2 (guesser). Waiting for word...\n")

    # get the secret word from Player 1
    secret = conn1.recv(1024).decode().strip().lower()

    while len(secret) < 4 or len(secret) > 6 or not secret.isalpha():
        conn1.sendall(b"Invalid word. Enter a 4 to 6 letter word:")
        secret = conn1.recv(1024).decode().strip().lower()

    word_length = len(secret)
    current_state = "*" * word_length

    conn2.sendall(f"Guess the {word_length} letter word!\n".encode())

  #  print("Received secret:", secret) #check
    # game loop
    while True:
        conn2.sendall(b"Enter guess:\n")
        guess = conn2.recv(1024).decode().strip().lower()

        if len(guess) != word_length or not guess.isalpha():
            conn2.sendall(f"Invalid guess. Enter a {word_length}-letter word.\n".encode())
            continue

        current_state, correct, wrong = compare_words(secret, guess, current_state)

        if guess == secret:
            conn2.sendall(f"Correct! The word was '{secret}'\n".encode())
            conn1.sendall(b"Your word was guessed!\n")
            break
        else:
            msg = (
                f"Word: {current_state}\n"
                f"{correct} correct position\n"
                f"{wrong} wrong position\n"
            )
            conn2.sendall(msg.encode())

    conn1.close()
    conn2.close()
