import socket

HOST = "127.0.0.1"
PORT = 65434

MAX_GUESSES = 10

#  protocol helpers 
# every message the server sends ends with a newline.
# when the server wants the client to read a line of input it first sends
# the line "INPUT:<prompt text>\n". the client then prompts the user and
# sends back "<user text>\n".

def send(conn, text: str):
    # send a plain display message to the client (no input expected)
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

    # pass 1 – find letters in the right position
    for i in range(len(secret)):
        if guess[i] == secret[i]:
            revealed[i]    = guess[i]
            correc
