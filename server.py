import socket

HOST = "127.0.0.1"
PORT = 65434

MAX_GUESSES = 10

# BIG FIX FROM BEFORE
# when the server wants the client to read a line of input it first sends
# the line "INPUT:<prompt text>\n". the client then prompts the user and
# sends back "<user text>\n".

def send(conn, text: str):
    # send message to the client
    conn.sendall((text + "\n").encode())

def ask(conn, prompt: str) -> str:
    # send an input prompt to the client and return the user's stripped reply
    conn.sendall(f"INPUT:{prompt}\n".encode())
    return conn.recv(1024).decode().strip()


# game logic

def compare_words(secret: str, guess: str, current_state: str):
    # compare the guess against the secret word and update the revealed state
    revealed = list(current_state)
    correct_spot = 0
    wrong_spot = 0

    # track which letters in the secret and guess have already been matched
    secret_used = [False] * len(secret)
    guess_used  = [False] * len(guess)

    # 1: find letters in the right position
    for i in range(len(secret)):
        if guess[i] == secret[i]:
            revealed[i]    = guess[i]
            correct_spot  += 1
            secret_used[i] = True
            guess_used[i]  = True

    # 2: find correct letters in the wrong position
    for i in range(len(guess)):
        if guess_used[i]:
            continue
        for j in range(len(secret)):
            if not secret_used[j] and guess[i] == secret[j]:
                wrong_spot    += 1
                secret_used[j] = True
                break

    # return the updated revealed word and the counts
    return "".join(revealed), correct_spot, wrong_spot


# server

def run_server():
    # create a TCP socket, bind it to the host/port, and wait for two players
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen()
        print(f"Server listening on {HOST}:{PORT} – waiting for 2 players…")

        # accept/connect player 1 and give role
        conn1, addr1 = srv.accept()
        print(f"Player 1 connected: {addr1}")
        send(conn1, "=== WORDUEL ===")
        send(conn1, "You are Player 1 — the Wordsetter. Waiting for Player 2 to connect…")

        # accept player 2 and give them role
        conn2, addr2 = srv.accept()
        print(f"Player 2 connected: {addr2}")
        send(conn2, "=== WORDUEL ===")
        send(conn2, "You are Player 2 — the Guesser. Waiting for Player 1 to set a word…")

        # notify player 1 that player 2 has joined
        send(conn1, "Player 2 has joined!")

        # get secret word from player 1
        # keep asking until player 1 provides a valid 4–6 letter alphabetic word
        secret = ask(conn1, "Enter a 4–6 letter word: ")
        while len(secret) < 4 or len(secret) > 6 or not secret.isalpha():
            secret = ask(conn1, "Invalid. Please enter a 4–6 letter word: ")
        secret = secret.lower()

        # initialize the hidden word state with asterisks
        word_length   = len(secret)
        current_state = "*" * word_length

        # confirm the word to player 1 and start the game for player 2
        send(conn1, f"Great! Your word '{secret}' is set. Watch the guesses come in…")
        send(conn2, f"\nGame on! Guess the {word_length}-letter word. You have {MAX_GUESSES} attempts.")
        send(conn2, f"Word: {current_state}")

        # guessing loop
        for attempt in range(1, MAX_GUESSES + 1):
            # ask player 2 for a guess and validate it
            guess = ask(conn2, f"Guess #{attempt}/{MAX_GUESSES}: ")

            # keep re-asking if the guess is the wrong length or contains non-letters
            while len(guess) != word_length or not guess.isalpha():
                send(conn2, f"Invalid – please enter a {word_length}-letter word.")
                guess = ask(conn2, f"Guess #{attempt}/{MAX_GUESSES}: ")
            guess = guess.lower()

            # show the guess to player 1 as it comes in
            send(conn1, f"  Guess {attempt}: {guess.upper()}")

            # evaluate the guess and update the revealed state
            current_state, correct, wrong = compare_words(secret, guess, current_state)

            if guess == secret:
                # player 2 guessed correctly – notify both players and end the game
                send(conn2, f"\n Correct! You got it in {attempt} attempt{'s' if attempt > 1 else ''}!")
                send(conn2, f"The word was: {secret.upper()}")
                send(conn1, f"\n Your word was guessed in {attempt} attempt{'s' if attempt > 1 else ''}!")
                break
            else:
                # send player 2 the updated state and hint counts
                remaining = MAX_GUESSES - attempt
                msg = (
                    f"\nWord:  {current_state}\n"
                    f"  {correct} correct position\n"
                    f"  {wrong} right letter, wrong spot\n"
                    f"  {remaining} guess{'es' if remaining != 1 else ''} remaining"
                )
                send(conn2, msg)
                # send player 1 summary of the result
                send(conn1, f"     → state: {current_state}  ({correct} right spot, {wrong} wrong spot)")
        else:
            # player 2 used all guesses without winning so reveal the word
            send(conn2, f"\n Out of guesses! The word was: {secret.upper()}")
            send(conn1, f"\n Player 2 ran out of guesses! Your word '{secret.upper()}' survived!")

        # send end message and shut down the connection
        send(conn1, "\n Game over. Thanks for playing!")
        send(conn2, "\n Game over. Thanks for playing!")

        conn1.close()
        conn2.close()
        print("Game finished.")


if __name__ == "__main__":
    run_server()

