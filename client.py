import socket
import threading
import tkinter as tk
from tkinter import font as tkfont

# ── network config (must match server.py) ──────────────────────────────────────
HOST = "127.0.0.1"
PORT = 65434

# ── colour palette  (retro amber-on-black terminal) ───────────────────────────
BG          = "#0a0a0a"   # near-black background
SURFACE     = "#111111"   # slightly lifted panels
AMBER       = "#ffb300"   # primary amber glow
AMBER_DIM   = "#7a5500"   # dimmed amber for empty slots
GREEN       = "#39ff14"   # neon green for correct-position letters
YELLOW      = "#ffe135"   # yellow for wrong-position hints
RED         = "#ff3c3c"   # error / out-of-guesses
BORDER      = "#2a2a2a"   # subtle panel borders
TEXT_MUTED  = "#555555"   # muted label text

# ── layout constants ───────────────────────────────────────────────────────────
BOX_W, BOX_H = 58, 68    # pixel size of each letter tile
BOX_GAP      = 8          # gap between tiles
MAX_COLS     = 6          # maximum word length supported
MAX_ROWS     = 10         # maximum guess rows to pre-render
PANEL_W      = 460        # total window width


class WorduelGUI:
    """
    tkinter GUI that replaces the plain-text client.
    It connects to the server over TCP, reads MSG / INPUT lines from the
    server (same protocol as the terminal client), and drives the interface.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("WORDUEL")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        # game state
        self.word_length   = 0       # set once the server tells us
        self.current_row   = 0       # which guess row we are on
        self.current_state = []      # list of chars ('*' or revealed letter)
        self.role          = None    # "setter" or "guesser" – detected from server msgs
        self.game_over     = False
        self.pending_input = False   # True while waiting for the user to submit

        # socket + thread
        self.sock   = None
        self.buffer = ""

        # build all UI widgets
        self._build_ui()

        # connect to the server in a background thread so the GUI stays responsive
        threading.Thread(target=self._connect, daemon=True).start()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        """Create every widget.  Letter grid is created later once we know word length."""

        # custom fonts
        self.font_title  = tkfont.Font(family="Courier", size=22, weight="bold")
        self.font_tile   = tkfont.Font(family="Courier", size=26, weight="bold")
        self.font_label  = tkfont.Font(family="Courier", size=9)
        self.font_input  = tkfont.Font(family="Courier", size=14)
        self.font_log    = tkfont.Font(family="Courier", size=10)
        self.font_hint   = tkfont.Font(family="Courier", size=11)

        # ── title bar ─────────────────────────────────────────────────────────
        title_frame = tk.Frame(self.root, bg=BG)
        title_frame.pack(fill="x", padx=20, pady=(18, 4))

        tk.Label(
            title_frame, text="W O R D U E L", font=self.font_title,
            bg=BG, fg=AMBER
        ).pack(side="left")

        self.role_badge = tk.Label(
            title_frame, text="connecting…", font=self.font_label,
            bg=BG, fg=TEXT_MUTED
        )
        self.role_badge.pack(side="right", pady=6)

        tk.Frame(self.root, bg=AMBER_DIM, height=1).pack(fill="x", padx=20)

        # ── letter grid canvas ────────────────────────────────────────────────
        # canvas is sized generously; tiles are drawn after word length is known
        self.canvas = tk.Canvas(
            self.root, bg=BG, highlightthickness=0,
            width=PANEL_W, height=(BOX_H + BOX_GAP) * MAX_ROWS + BOX_GAP
        )
        self.canvas.pack(padx=20, pady=12)

        # tile rectangle and letter text IDs stored as 2-D lists
        self.tile_rects = []
        self.tile_texts = []

        # ── hint strip (correct / misplaced counts) ───────────────────────────
        hint_frame = tk.Frame(self.root, bg=BG)
        hint_frame.pack(fill="x", padx=24, pady=(0, 6))

        self.lbl_correct = tk.Label(
            hint_frame, text="", font=self.font_hint, bg=BG, fg=GREEN, anchor="w"
        )
        self.lbl_correct.pack(side="left")

        self.lbl_wrong = tk.Label(
            hint_frame, text="", font=self.font_hint, bg=BG, fg=YELLOW, anchor="w"
        )
        self.lbl_wrong.pack(side="left", padx=(16, 0))

        self.lbl_remaining = tk.Label(
            hint_frame, text="", font=self.font_hint, bg=BG, fg=TEXT_MUTED, anchor="e"
        )
        self.lbl_remaining.pack(side="right")

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x", padx=20)

        # ── input row ─────────────────────────────────────────────────────────
        input_frame = tk.Frame(self.root, bg=BG)
        input_frame.pack(fill="x", padx=20, pady=10)

        self.prompt_lbl = tk.Label(
            input_frame, text="", font=self.font_label,
            bg=BG, fg=TEXT_MUTED, anchor="w"
        )
        self.prompt_lbl.pack(fill="x")

        entry_row = tk.Frame(input_frame, bg=BG)
        entry_row.pack(fill="x", pady=(4, 0))

        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(
            entry_row,
            textvariable=self.entry_var,
            font=self.font_input,
            bg=SURFACE, fg=AMBER, insertbackground=AMBER,
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground=AMBER_DIM,
            highlightcolor=AMBER,
            width=18,
            state="disabled"
        )
        self.entry.pack(side="left", ipady=7, padx=(0, 10))
        # submit on Enter key as well as the button
        self.entry.bind("<Return>", lambda e: self._submit())

        self.submit_btn = tk.Button(
            entry_row,
            text="SEND  ▶",
            font=self.font_label,
            bg=AMBER, fg=BG,
            activebackground="#ffcf40", activeforeground=BG,
            relief="flat", bd=0, padx=14, pady=6,
            cursor="hand2",
            command=self._submit,
            state="disabled"
        )
        self.submit_btn.pack(side="left")

        # ── scrolling log panel ───────────────────────────────────────────────
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x", padx=20)

        log_frame = tk.Frame(self.root, bg=BG)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(6, 14))

        tk.Label(
            log_frame, text="SERVER LOG", font=self.font_label,
            bg=BG, fg=TEXT_MUTED
        ).pack(anchor="w")

        self.log_text = tk.Text(
            log_frame,
            font=self.font_log,
            bg=SURFACE, fg=TEXT_MUTED,
            relief="flat", bd=0,
            highlightthickness=0,
            height=6,
            state="disabled",
            wrap="word",
            cursor="arrow"
        )
        self.log_text.pack(fill="both", expand=True, pady=(4, 0))

        # colour tags for the log
        self.log_text.tag_config("amber",  foreground=AMBER)
        self.log_text.tag_config("green",  foreground=GREEN)
        self.log_text.tag_config("yellow", foreground=YELLOW)
        self.log_text.tag_config("red",    foreground=RED)
        self.log_text.tag_config("muted",  foreground=TEXT_MUTED)

    # ── grid creation (called once word length is known) ──────────────────────

    def _build_grid(self, word_length: int, max_rows: int):
        """Draw MAX_ROWS × word_length tile placeholders on the canvas."""
        self.word_length = word_length
        self.current_state = ["*"] * word_length
        self.tile_rects = []
        self.tile_texts = []

        total_w = word_length * BOX_W + (word_length - 1) * BOX_GAP
        x_start = (PANEL_W - total_w) // 2

        for row in range(max_rows):
            row_rects = []
            row_texts = []
            for col in range(word_length):
                x = x_start + col * (BOX_W + BOX_GAP)
                y = BOX_GAP + row * (BOX_H + BOX_GAP)

                rect_id = self.canvas.create_rectangle(
                    x, y, x + BOX_W, y + BOX_H,
                    fill=SURFACE, outline=AMBER_DIM, width=1
                )
                text_id = self.canvas.create_text(
                    x + BOX_W // 2, y + BOX_H // 2,
                    text="", font=self.tile_font if hasattr(self, "tile_font") else self.font_tile,
                    fill=AMBER_DIM
                )
                row_rects.append(rect_id)
                row_texts.append(text_id)

            self.tile_rects.append(row_rects)
            self.tile_texts.append(row_texts)

        # resize canvas height to fit exactly the rows we need
        canvas_h = max_rows * (BOX_H + BOX_GAP) + BOX_GAP
        self.canvas.config(height=canvas_h)

    def _update_grid_row(self, row: int, state: list[str]):
        """
        Paint a completed guess row using the revealed state.
        Green  = correct position (letter shown, not '*')
        Dimmed = still hidden ('*')
        """
        for col, ch in enumerate(state):
            rect_id = self.tile_rects[row][col]
            text_id = self.tile_texts[row][col]

            if ch == "*":
                self.canvas.itemconfig(rect_id, fill=SURFACE, outline=AMBER_DIM)
                self.canvas.itemconfig(text_id, text="✦", fill=AMBER_DIM)
            else:
                # revealed letter – flash green
                self.canvas.itemconfig(rect_id, fill="#0d2b0d", outline=GREEN)
                self.canvas.itemconfig(text_id, text=ch.upper(), fill=GREEN)

    # ── networking ─────────────────────────────────────────────────────────────

    def _connect(self):
        """Run in a daemon thread – connects to the server and reads lines."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((HOST, PORT))
            self._log("Connected to server.", tag="amber")

            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    # server closed the connection
                    self.root.after(0, self._on_disconnected)
                    break

                self.buffer += chunk.decode()

                # process every complete newline-terminated line in the buffer
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    self.root.after(0, self._handle_line, line)

        except ConnectionRefusedError:
            self.root.after(0, self._on_connect_error)

    def _send(self, text: str):
        """Send a line of text to the server."""
        if self.sock:
            self.sock.sendall((text + "\n").encode())

    # ── line handling (runs on the main GUI thread via root.after) ─────────────

    def _handle_line(self, line: str):
        """Dispatch an incoming server line to the right handler."""
        if line.startswith("INPUT:"):
            # server is requesting input from the user
            prompt = line[len("INPUT:"):]
            self._request_input(prompt)
        else:
            # plain display message
            self._handle_msg(line)

    def _handle_msg(self, msg: str):
        """Process a plain MSG line: update game state and UI."""
        self._log(msg, tag="muted")

        # ── detect role from greeting messages ────────────────────────────────
        if "Player 1" in msg and "Wordsetter" in msg:
            self.role = "setter"
            self.role_badge.config(text="🔒  WORD SETTER", fg=AMBER)
        elif "Player 2" in msg and "Guesser" in msg:
            self.role = "guesser"
            self.role_badge.config(text="🔍  GUESSER", fg=GREEN)

        # ── detect word length from "Guess the N-letter word" message ─────────
        if "letter word" in msg and self.word_length == 0:
            for token in msg.split():
                if token.isdigit():
                    wlen = int(token)
                    if 4 <= wlen <= 6:
                        self._build_grid(wlen, MAX_ROWS)
                        break

        # ── parse the "Word:  <state>" line to update tile display ────────────
        if msg.strip().startswith("Word:"):
            state_str = msg.strip()[len("Word:"):].strip()
            if state_str and self.word_length > 0 and len(state_str) == self.word_length:
                self.current_state = list(state_str)
                # update the CURRENT row with the new revealed state
                row = max(0, self.current_row - 1)
                self._update_grid_row(row, self.current_state)

        # ── parse hint counts from feedback lines ─────────────────────────────
        if "correct position" in msg:
            try:
                n = int(msg.strip().split()[0])
                self.lbl_correct.config(text=f"✅  {n} correct position{'s' if n != 1 else ''}")
            except ValueError:
                pass

        if "right letter, wrong spot" in msg:
            try:
                n = int(msg.strip().split()[0])
                self.lbl_wrong.config(text=f"🔄  {n} wrong spot{'s' if n != 1 else ''}")
            except ValueError:
                pass

        if "guess" in msg and "remaining" in msg:
            self.lbl_remaining.config(text=msg.strip(), fg=TEXT_MUTED)

        # ── win / loss detection ──────────────────────────────────────────────
        if "Correct!" in msg or "guessed" in msg:
            self._log(msg, tag="green")
            self._end_game(won=True)

        if "Out of guesses" in msg or "survived" in msg:
            self._log(msg, tag="red")
            self._end_game(won=False)

        if "Game over" in msg:
            self._disable_input()

    def _request_input(self, prompt: str):
        """Enable the input field and show the prompt label."""
        self.pending_input = True
        self.prompt_lbl.config(text=prompt.strip())
        self.entry.config(state="normal")
        self.submit_btn.config(state="normal")
        self.entry.focus_set()

    def _submit(self):
        """Called when the user presses Enter or clicks SEND."""
        if not self.pending_input:
            return

        text = self.entry_var.get().strip()
        if not text:
            return

        self.pending_input = False
        self.entry_var.set("")
        self.entry.config(state="disabled")
        self.submit_btn.config(state="disabled")
        self.prompt_lbl.config(text="")

        self._log(f"> {text}", tag="amber")
        self._send(text)

        # if we're the guesser and the word length is set, paint the guess row
        if self.role == "guesser" and self.word_length > 0:
            guess = text.lower()
            if len(guess) == self.word_length and guess.isalpha():
                self._paint_guess_row(self.current_row, guess)
                self.current_row += 1

    def _paint_guess_row(self, row: int, guess: str):
        """Temporarily fill a row with the typed guess in amber (pre-reveal)."""
        if row >= len(self.tile_rects):
            return
        for col, ch in enumerate(guess):
            self.canvas.itemconfig(self.tile_rects[row][col], fill="#1a1200", outline=AMBER)
            self.canvas.itemconfig(self.tile_texts[row][col], text=ch.upper(), fill=AMBER)

    # ── end-game helpers ──────────────────────────────────────────────────────

    def _end_game(self, won: bool):
        """Lock the UI and show the outcome colour on the role badge."""
        self.game_over = True
        self._disable_input()
        colour = GREEN if won else RED
        result = "YOU WON 🎉" if won else "GAME OVER 💀"
        self.role_badge.config(text=result, fg=colour)
        self.lbl_remaining.config(text="", fg=colour)

    def _disable_input(self):
        self.entry.config(state="disabled")
        self.submit_btn.config(state="disabled")

    # ── connection status helpers ──────────────────────────────────────────────

    def _on_disconnected(self):
        self._log("Disconnected from server.", tag="red")
        self._disable_input()
        self.role_badge.config(text="disconnected", fg=RED)

    def _on_connect_error(self):
        self._log(f"Could not connect to {HOST}:{PORT}. Is the server running?", tag="red")
        self.role_badge.config(text="connection failed", fg=RED)

    # ── log helper ─────────────────────────────────────────────────────────────

    def _log(self, text: str, tag: str = "muted"):
        """Append a line to the scrolling server log."""
        self.log_text.config(state="normal")
        self.log_text.insert("end", text + "\n", tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")


# ── entry point ────────────────────────────────────────────────────────────────

def run_client():
    root = tk.Tk()
    app = WorduelGUI(root)
    root.mainloop()


if __name__ == "__main__":
    run_client()





'''
# import the socket module for network communication
import socket

# define the host address and port number to connect to
HOST = "127.0.0.1"
PORT = 65434


def run_client():
    # create a TCP socket and connect to the server
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        # buffer to accumulate incoming data until we have complete lines
        buffer = ""

        # keep receiving data from the server until the connection closes
        while True:
            chunk = s.recv(4096)
            if not chunk:
                # server closed the connection –> game over
                break

            # decode the incoming bytes and append them to the buffer
            buffer += chunk.decode()

            # process all complete lines in the buffer
            while "\n" in buffer:
                # split off the first complete line, leaving the rest in the buffer
                line, buffer = buffer.split("\n", 1)

                if line.startswith("INPUT:"):
                    # server wants input – print the prompt and read from stdin
                    prompt = line[len("INPUT:"):]
                    user_input = input(prompt)
                    # send the user's response back to the server
                    s.sendall((user_input + "\n").encode())
                else:
                    # oprint plain display line
                    print(line)


# entry point: run the client when this script is executed directly
if __name__ == "__main__":
    run_client()
'''
