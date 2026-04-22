import socket
import time
from wordlist import build_wordlist

HOST = "127.0.0.1"
PORT = 65434

MAX_GUESSES = 10

# ── Protocol helpers ───────────────────────────────────────────────────────────

def send(conn, text: str):
    """Send a plain display message to the client."""
    conn.sendall((text + "\n").encode())

def ask(conn, prompt: str) -> str:
    """Ask the client for input and return the stripped reply."""
    conn.sendall(f"INPUT:{prompt}\n".encode())
    return conn.recv(1024).decode().strip()


# ── Game logic ─────────────────────────────────────────────────────────────────

def compare_words(secret: str, guess: str, current_state: str):
    """Return (new_state, correct_spot_count, wrong_spot_count)."""
    revealed = list(current_state)
    correct_spot = 0
    wrong_spot = 0

    secret_used = [False] * len(secret)
    guess_used  = [False] * len(guess)

    for i in range(len(secret)):
        if guess[i] == secret[i]:
            revealed[i]    = guess[i]
            correct_spot  += 1
            secret_used[i] = True
            guess_used[i]  = True

    for i in range(len(guess)):
        if guess_used[i]:
            continue
        for j in range(len(secret)):
            if not secret_used[j] and guess[i] == secret[j]:
                wrong_spot    += 1
                secret_used[j] = True
                break

    return "".join(revealed), correct_spot, wrong_spot


def ai_guess(candidates: list, current_state: str, wrong_spot_letters: list) -> str:
    """Pick the best guess by letter frequency scoring over remaining candidates."""
    if not candidates:
        return "crane"

    freq: dict = {}
    for word in candidates:
        for ch in set(word):
            freq[ch] = freq.get(ch, 0) + 1

    def score(word):
        return sum(freq.get(ch, 0) for ch in set(word))

    return max(candidates, key=score)


def filter_candidates(candidates, guess, current_state, wrong_spot_letters, eliminated):
    """Narrow candidates based on all feedback received so far."""
    new_candidates = []
    for word in candidates:
        valid = True

        # Revealed letters must be in the correct position
        for i, ch in enumerate(current_state):
            if ch != '*' and word[i] != ch:
                valid = False
                break
        if not valid:
            continue

        # Wrong-spot letters must appear somewhere (but not at that position)
        for (ch, pos) in wrong_spot_letters:
            if ch not in word or word[pos] == ch:
                valid = False
                break
        if not valid:
            continue

        # Eliminated letters must not appear (unless they're also a revealed letter)
        revealed_chars = set(ch for ch in current_state if ch != '*')
        for ch in eliminated:
            if ch not in revealed_chars and ch in word:
                valid = False
                break

        if valid:
            new_candidates.append(word)

    return new_candidates


# ── Server ─────────────────────────────────────────────────────────────────────

def run_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen()
        print("=== WORDUEL SERVER (AI Guesser) ===")
        print(f"Listening on {HOST}:{PORT} — waiting for player to connect…\n")

        conn, addr = srv.accept()
        print(f"Player connected: {addr}\n")

        send(conn, "=== WORDUEL ===")
        send(conn, "You are the Word Setter. The SERVER will try to guess your word.")
        send(conn, "")

        # Get the secret word
        secret = ask(conn, "Enter a 4–6 letter word: ").lower()
        while len(secret) < 4 or len(secret) > 6 or not secret.isalpha():
            secret = ask(conn, "Invalid. Enter a 4–6 letter word: ").lower()

        word_length   = len(secret)
        current_state = "*" * word_length

        send(conn, f"\nChallenge accepted! Trying to guess your {word_length}-letter word…\n")
        print(f"[Secret word: '{secret}']")

        candidates         = build_wordlist(word_length)
        wrong_spot_letters = []   # (char, position) pairs
        eliminated         = set()
        print(f"[Starting with {len(candidates)} candidates]\n")

        for attempt in range(1, MAX_GUESSES + 1):
            guess = ai_guess(candidates, current_state, wrong_spot_letters)

            print(f"  Attempt {attempt}: {guess}  ({len(candidates)} candidates)")
            time.sleep(0.6)
            send(conn, f"Attempt {attempt}/{MAX_GUESSES}:  {guess.upper()}")

            current_state, correct, wrong = compare_words(secret, guess, current_state)

            if guess == secret:
                send(conn, f"\n  {current_state}")
                send(conn, f"\n🎉 I got it in {attempt} attempt{'s' if attempt != 1 else ''}!")
                send(conn, f"The word was: {secret.upper()}")
                send(conn, "\n--- Game over. Thanks for playing! ---")
                print(f"\n[AI won in {attempt} attempts]")
                break

            remaining = MAX_GUESSES - attempt
            send(conn, f"  Word:  {current_state}")
            send(conn, f"  ✅ {correct} correct spot  |  🔄 {wrong} wrong spot  |  {remaining} guess{'es' if remaining != 1 else ''} left\n")

            # Track eliminated and wrong-spot letters from this guess
            secret_used = [False] * len(secret)
            guess_used  = [False] * len(guess)
            for i in range(len(secret)):
                if guess[i] == secret[i]:
                    secret_used[i] = True
                    guess_used[i]  = True
            for i in range(len(guess)):
                if guess_used[i]:
                    continue
                matched = False
                for j in range(len(secret)):
                    if not secret_used[j] and guess[i] == secret[j]:
                        wrong_spot_letters.append((guess[i], i))
                        secret_used[j] = True
                        matched = True
                        break
                if not matched:
                    eliminated.add(guess[i])

            candidates = filter_candidates(candidates, guess, current_state, wrong_spot_letters, eliminated)
            if secret not in candidates:
                candidates.append(secret)  # always keep the answer reachable

        else:
            send(conn, f"\n💀 I ran out of guesses! Your word '{secret.upper()}' wins!")
            send(conn, "\n--- Game over. Thanks for playing! ---")
            print(f"\n[AI lost — '{secret}' was not guessed]")

        conn.close()
        print("Game finished.")


if __name__ == "__main__":
    run_server()
