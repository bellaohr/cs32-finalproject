import socket

HOST = "127.0.0.1"
PORT = 65434

MAX_GUESSES = 10

# Every message the server sends ends with a newline.
# When the server wants the client to read a line of input it first sends
# the line "INPUT:<prompt text>\n".  The client then prompts the user and
# sends back "<user text>\n".

def send(conn, text: str):
    """Send a plain display message (no input expected)."""
    conn.sendall((text + "\n").encode())

def ask(conn, prompt: str) -> str:
    """Ask the client for input and return the stripped reply."""
    conn.sendall(f"INPUT:{prompt}\n".encode())
    return conn.recv(1024).decode().strip()


#  logic

def compare_words(secret: str, guess: str, current_state: str):
    """Return (new_state, correct_spot_count, wrong_spot_count)."""
    revealed = list(current_state)
    correct_spot = 0
    wrong_spot = 0

    secret_used = [False] * len(secret)
    guess_used  = [False] * len(guess)

    # Pass 1 – right letter, right position
    for i in range(len(secret)):
        if guess[i] == secret[i]:
            revealed[i]    = guess[i]
            correct_spot  += 1
            secret_used[i] = True
            guess_used[i]  = True

    # Pass 2 – right letter, wrong position
    for i in range(len(guess)):
        if guess_used[i]:
            continue
        for j in range(len(secret)):
            if not secret_used[j] and guess[i] == secret[j]:
                wrong_spot    += 1
                secret_used[j] = True
                break

    return "".join(revealed), correct_spot, wrong_spot


# server

def run_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen()
        print(f"Server listening on {HOST}:{PORT} – waiting for 2 players…")

        conn1, addr1 = srv.accept()
        print(f"Player 1 connected: {addr1}")
        send(conn1, "=== WORDUEL ===")
        send(conn1, "You are Player 1 — the Word Setter.")

        conn2, addr2 = srv.accept()
        print(f"Player 2 connected: {addr2}")
        send(conn2, "=== WORDUEL ===")
        send(conn2, "You are Player 2 — the Guesser.")
        send(conn2, "Waiting for Player 1 to set a word…")

        # ── Get secret word from Player 1 ─────────────────────────────────────
        secret = ask(conn1, "Enter a 4–6 letter word: ")
        while len(secret) < 4 or len(secret) > 6 or not secret.isalpha():
            secret = ask(conn1, "Invalid. Please enter a 4–6 letter word: ")
        secret = secret.lower()

        word_length   = len(secret)
        current_state = "*" * word_length

        send(conn1, f"Great! Your word '{secret}' is set. Watch the guesses come in…")
        send(conn2, f"\nGame on! Guess the {word_length}-letter word. You have {MAX_GUESSES} attempts.")
        send(conn2, f"Word: {current_state}")

        # guess loop
        for attempt in range(1, MAX_GUESSES + 1):
            guess = ask(conn2, f"Guess #{attempt}/{MAX_GUESSES}: ")

            # Validate
            while len(guess) != word_length or not guess.isalpha():
                send(conn2, f"Invalid – please enter a {word_length}-letter word.")
                guess = ask(conn2, f"Guess #{attempt}/{MAX_GUESSES}: ")
            guess = guess.lower()

            # Notify Player 1
            send(conn1, f"  Guess {attempt}: {guess.upper()}")

            # Evaluate
            current_state, correct, wrong = compare_words(secret, guess, current_state)

            if guess == secret:
                send(conn2, f"\n Correct! You got it in {attempt} attempt{'s' if attempt > 1 else ''}!")
                send(conn2, f"The word was: {secret.upper()}")
                send(conn1, f"\n Your word was guessed in {attempt} attempt{'s' if attempt > 1 else ''}!")
                break
            else:
                remaining = MAX_GUESSES - attempt
                msg = (
                    f"\nWord:  {current_state}\n"
                    f"  {correct} correct position\n"
                    f"  {wrong} right letter, wrong spot\n"
                    f"  {remaining} guess{'es' if remaining != 1 else ''} remaining"
                )
                send(conn2, msg)
                send(conn1, f"     → state: {current_state}  ({correct} right spot, {wrong} wrong spot)")
        else:
            # Ran out of guesses
            send(conn2, f"\n Out of guesses! The word was: {secret.upper()}")
            send(conn1, f"\n Player 2 ran out of guesses! Your word '{secret.upper()}' survived!")

        send(conn1, "\n--- Game over. Thanks for playing! ---")
        send(conn2, "\n--- Game over. Thanks for playing! ---")

        conn1.close()
        conn2.close()
        print("Game finished.")


if __name__ == "__main__":
    run_server()
