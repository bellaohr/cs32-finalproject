"""
client_web.py  –  Flask web interface for Worduel
==================================================
Run this instead of client.py.  It connects to the game server over TCP
(same HOST / PORT as before) and serves a browser UI on port 5000.

Usage
-----
    pip install flask
    python client_web.py

Then open the URL that Codespaces forwards for port 5000.
Two players each open the page in their own browser tab.
"""

import socket
import threading
import queue
import time
from flask import Flask, Response, request, jsonify, render_template_string

# ── network config (must match server.py) ─────────────────────────────────────
HOST = "127.0.0.1"
PORT = 65434

# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__)

# ── shared state between the TCP thread and the Flask routes ──────────────────
# queue of SSE event dicts to push to the browser
event_queue: queue.Queue = queue.Queue()

# when the server sends INPUT: the TCP thread parks the prompt here and blocks
# until the browser submits an answer via POST /send
pending_prompt: str | None = None
pending_answer: queue.Queue = queue.Queue()   # browser puts the answer here

# TCP socket (set once connected)
sock: socket.socket | None = None
connected = False
connect_error: str | None = None


# ── SSE helper ─────────────────────────────────────────────────────────────────

def push(event_type: str, data: str):
    """Put an event onto the queue so SSE can stream it to the browser."""
    event_queue.put({"type": event_type, "data": data})


# ── TCP thread ─────────────────────────────────────────────────────────────────

def tcp_thread():
    """
    Runs in a daemon thread.
    Connects to the game server and processes lines exactly like client.py does,
    but instead of printing / calling input() it pushes SSE events and waits
    for the browser to supply answers.
    """
    global sock, connected, connect_error, pending_prompt

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        connected = True
        push("status", "connected")

        buffer = ""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                push("status", "disconnected")
                break

            buffer += chunk.decode()

            # process every complete newline-terminated line
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)

                if line.startswith("INPUT:"):
                    # server wants input – tell the browser and wait for an answer
                    prompt = line[len("INPUT:"):]
                    pending_prompt = prompt
                    push("input_request", prompt)

                    # block this thread until the browser POSTs an answer
                    answer = pending_answer.get()
                    pending_prompt = None

                    # send the answer back to the game server
                    sock.sendall((answer + "\n").encode())
                    push("sent", answer)

                else:
                    # plain display message – forward to browser
                    push("msg", line)

    except ConnectionRefusedError:
        connect_error = f"Could not connect to game server at {HOST}:{PORT}. Is server.py running?"
        push("error", connect_error)
    except Exception as exc:
        push("error", str(exc))


# ── Flask routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the single-page game UI."""
    return render_template_string(HTML)


@app.route("/stream")
def stream():
    """
    Server-Sent Events endpoint.
    The browser connects here once and receives a live stream of game events.
    """
    def generate():
        # drain any events already queued before the browser connected
        while True:
            try:
                evt = event_queue.get(timeout=30)
                yield f"event: {evt['type']}\ndata: {evt['data']}\n\n"
            except queue.Empty:
                # send a keepalive comment so the connection stays open
                yield ": keepalive\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/send", methods=["POST"])
def send():
    """
    The browser POSTs the player's answer here.
    We put it on pending_answer so the TCP thread can forward it to the server.
    """
    data = request.get_json()
    answer = (data or {}).get("answer", "").strip()
    if answer:
        pending_answer.put(answer)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "empty answer"}), 400


@app.route("/status")
def status():
    return jsonify({
        "connected": connected,
        "error": connect_error,
        "waiting_for_input": pending_prompt is not None,
        "prompt": pending_prompt,
    })


# ── HTML / CSS / JS (single-page UI) ──────────────────────────────────────────

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>WORDUEL</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@700;900&display=swap');

:root {
  --bg:      #080c10;
  --surface: #0e1318;
  --border:  #1c2a36;
  --amber:   #f0a500;
  --amber-d: #3d2900;
  --green:   #00e676;
  --yellow:  #ffe135;
  --red:     #ff3d3d;
  --muted:   #3a5068;
  --text:    #c8dde8;
}

* { margin:0; padding:0; box-sizing:border-box; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Share Tech Mono', monospace;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  /* subtle scanline texture */
  background-image: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0,0,0,0.18) 2px,
    rgba(0,0,0,0.18) 4px
  );
}

/* ── header ─────────────────────────────────────────────────────────────── */
header {
  width: 100%;
  max-width: 560px;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding: 22px 0 10px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
}

.logo {
  font-family: 'Orbitron', sans-serif;
  font-weight: 900;
  font-size: 2rem;
  letter-spacing: 0.12em;
  color: var(--amber);
  text-shadow: 0 0 18px rgba(240,165,0,0.5);
}

#roleBadge {
  font-size: 0.7rem;
  letter-spacing: 0.15em;
  color: var(--muted);
  text-transform: uppercase;
  padding-bottom: 4px;
  transition: color 0.4s;
}

/* ── main layout ────────────────────────────────────────────────────────── */
main {
  width: 100%;
  max-width: 560px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-bottom: 40px;
}

/* ── tile grid ──────────────────────────────────────────────────────────── */
#grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.tile-row {
  display: flex;
  gap: 8px;
}

.tile {
  width: 58px;
  height: 66px;
  border: 1px solid var(--border);
  background: var(--surface);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Orbitron', sans-serif;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--muted);
  border-radius: 4px;
  transition: background 0.35s, border-color 0.35s, color 0.35s;
  position: relative;
  overflow: hidden;
}

/* corner pip decorations */
.tile::before, .tile::after {
  content: '';
  position: absolute;
  width: 5px; height: 5px;
  border-color: var(--border);
  border-style: solid;
  opacity: 0.5;
}
.tile::before { top: 3px; left: 3px; border-width: 1px 0 0 1px; }
.tile::after  { bottom: 3px; right: 3px; border-width: 0 1px 1px 0; }

.tile.active  { border-color: var(--amber); color: var(--amber); background: #12100a; }
.tile.hidden  { color: var(--muted); }
.tile.correct { background: #001f0f; border-color: var(--green); color: var(--green);
                box-shadow: 0 0 10px rgba(0,230,118,0.2); }
.tile.pop     { animation: pop 0.35s cubic-bezier(.34,1.56,.64,1) both; }

@keyframes pop {
  0%   { transform: scale(0.7) rotateX(60deg); opacity: 0; }
  100% { transform: scale(1)   rotateX(0deg);  opacity: 1; }
}

/* ── hint bar ───────────────────────────────────────────────────────────── */
#hintBar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  min-height: 42px;
  font-size: 0.8rem;
  letter-spacing: 0.05em;
}

#hintCorrect  { color: var(--green);  }
#hintWrong    { color: var(--yellow); }
#hintRemain   { color: var(--muted);  }

/* ── input panel ────────────────────────────────────────────────────────── */
#inputPanel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 14px;
}

#promptLabel {
  font-size: 0.7rem;
  color: var(--muted);
  letter-spacing: 0.15em;
  text-transform: uppercase;
  margin-bottom: 10px;
  min-height: 16px;
}

.input-row {
  display: flex;
  gap: 10px;
}

#answerInput {
  flex: 1;
  background: var(--bg);
  border: 1px solid var(--amber-d);
  border-radius: 4px;
  color: var(--amber);
  font-family: 'Share Tech Mono', monospace;
  font-size: 1.1rem;
  padding: 9px 12px;
  outline: none;
  letter-spacing: 0.12em;
  transition: border-color 0.2s;
  caret-color: var(--amber);
}
#answerInput:focus     { border-color: var(--amber); }
#answerInput:disabled  { opacity: 0.3; cursor: not-allowed; }

#sendBtn {
  background: var(--amber);
  color: #080c10;
  border: none;
  border-radius: 4px;
  font-family: 'Orbitron', sans-serif;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  padding: 0 18px;
  cursor: pointer;
  transition: background 0.2s, transform 0.1s;
}
#sendBtn:hover   { background: #ffc72c; }
#sendBtn:active  { transform: scale(0.96); }
#sendBtn:disabled { opacity: 0.25; cursor: not-allowed; transform: none; }

/* ── log ────────────────────────────────────────────────────────────────── */
#logWrap {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px 14px;
}

.log-label {
  font-size: 0.65rem;
  color: var(--muted);
  letter-spacing: 0.2em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

#log {
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--muted);
  max-height: 160px;
  overflow-y: auto;
  word-break: break-all;
}
#log::-webkit-scrollbar { width: 4px; }
#log::-webkit-scrollbar-thumb { background: var(--border); }

.log-msg    { color: var(--muted);  }
.log-sent   { color: var(--amber);  }
.log-event  { color: var(--green);  }
.log-error  { color: var(--red);    }

/* ── status overlay (before connect) ───────────────────────────────────── */
#statusOverlay {
  position: fixed; inset: 0;
  background: rgba(8,12,16,0.92);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  z-index: 99;
  font-family: 'Share Tech Mono', monospace;
}

#statusOverlay .status-title {
  font-family: 'Orbitron', sans-serif;
  font-size: 1.4rem;
  color: var(--amber);
  letter-spacing: 0.15em;
}

#statusOverlay .status-msg {
  font-size: 0.8rem;
  color: var(--muted);
  letter-spacing: 0.1em;
  text-align: center;
  max-width: 340px;
  line-height: 1.8;
}

.spinner {
  width: 28px; height: 28px;
  border: 2px solid var(--amber-d);
  border-top-color: var(--amber);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>

<!-- connecting overlay -->
<div id="statusOverlay">
  <div class="status-title">WORDUEL</div>
  <div class="spinner"></div>
  <div class="status-msg" id="overlayMsg">Connecting to game server…</div>
</div>

<header>
  <div class="logo">WORDUEL</div>
  <div id="roleBadge">waiting…</div>
</header>

<main>
  <!-- letter tile grid (rows added dynamically) -->
  <div id="grid"></div>

  <!-- hint bar -->
  <div id="hintBar">
    <span id="hintCorrect"></span>
    <span id="hintWrong"></span>
    <span id="hintRemain"></span>
  </div>

  <!-- input panel -->
  <div id="inputPanel">
    <div id="promptLabel">Waiting for server…</div>
    <div class="input-row">
      <input id="answerInput" type="text" maxlength="6"
             placeholder="type here…" autocomplete="off" disabled />
      <button id="sendBtn" disabled>SEND ▶</button>
    </div>
  </div>

  <!-- scrolling log -->
  <div id="logWrap">
    <div class="log-label">Server log</div>
    <div id="log"></div>
  </div>
</main>

<script>
// ── state ──────────────────────────────────────────────────────────────────
let wordLength   = 0;
let currentRow   = 0;
let currentState = [];   // array of chars, '*' or revealed letter
let totalRows    = 10;   // MAX_GUESSES from server.py
let role         = null; // 'setter' | 'guesser'
let gameOver     = false;

// ── DOM refs ───────────────────────────────────────────────────────────────
const grid        = document.getElementById('grid');
const hintCorrect = document.getElementById('hintCorrect');
const hintWrong   = document.getElementById('hintWrong');
const hintRemain  = document.getElementById('hintRemain');
const promptLabel = document.getElementById('promptLabel');
const answerInput = document.getElementById('answerInput');
const sendBtn     = document.getElementById('sendBtn');
const logEl       = document.getElementById('log');
const roleBadge   = document.getElementById('roleBadge');
const overlay     = document.getElementById('statusOverlay');
const overlayMsg  = document.getElementById('overlayMsg');

// ── grid helpers ───────────────────────────────────────────────────────────

function buildGrid(wlen) {
  wordLength   = wlen;
  currentState = Array(wlen).fill('*');
  grid.innerHTML = '';

  for (let r = 0; r < totalRows; r++) {
    const row = document.createElement('div');
    row.className  = 'tile-row';
    row.dataset.row = r;
    for (let c = 0; c < wlen; c++) {
      const tile = document.createElement('div');
      tile.className   = 'tile hidden';
      tile.dataset.col = c;
      tile.textContent = '✦';
      row.appendChild(tile);
    }
    grid.appendChild(row);
  }
}

function getTile(row, col) {
  const r = grid.querySelector(`.tile-row[data-row="${row}"]`);
  return r ? r.querySelector(`.tile[data-col="${col}"]`) : null;
}

// paint a row amber when the player types a guess (before server confirms)
function paintGuessRow(row, guess) {
  for (let c = 0; c < guess.length; c++) {
    const t = getTile(row, c);
    if (!t) continue;
    t.textContent = guess[c].toUpperCase();
    t.className   = 'tile active pop';
  }
}

// update a row with the revealed state returned by the server
function applyState(row, state) {
  for (let c = 0; c < state.length; c++) {
    const t = getTile(row, c);
    if (!t) continue;
    if (state[c] === '*') {
      t.textContent = '✦';
      t.className   = 'tile hidden';
    } else {
      t.textContent = state[c].toUpperCase();
      t.className   = 'tile correct pop';
    }
  }
}

// ── SSE – live event stream from Flask ────────────────────────────────────

const es = new EventSource('/stream');

es.addEventListener('status', e => {
  if (e.data === 'connected') {
    overlay.style.display = 'none';
    addLog('Connected to game server.', 'log-event');
  } else if (e.data === 'disconnected') {
    addLog('Disconnected from server.', 'log-error');
    setInputEnabled(false);
    roleBadge.textContent = 'disconnected';
    roleBadge.style.color  = 'var(--red)';
  }
});

es.addEventListener('msg', e => {
  const msg = e.data;
  addLog(msg, 'log-msg');
  handleMsg(msg);
});

es.addEventListener('input_request', e => {
  // server is asking for input – enable the field
  const prompt = e.data;
  promptLabel.textContent = prompt.trim();
  setInputEnabled(true);
  answerInput.focus();
});

es.addEventListener('sent', e => {
  addLog('> ' + e.data, 'log-sent');
});

es.addEventListener('error', e => {
  const msg = e.data || 'Connection error.';
  overlayMsg.textContent = msg;
  overlay.style.display  = 'flex';
  addLog(msg, 'log-error');
});

// ── message parser ─────────────────────────────────────────────────────────

function handleMsg(msg) {
  // detect role
  if (msg.includes('Player 1') && msg.includes('Wordsetter')) {
    role = 'setter';
    roleBadge.textContent = '🔒  WORD SETTER';
    roleBadge.style.color = 'var(--amber)';
  }
  if (msg.includes('Player 2') && msg.includes('Guesser')) {
    role = 'guesser';
    roleBadge.textContent = '🔍  GUESSER';
    roleBadge.style.color = 'var(--green)';
  }

  // detect word length from "Guess the N-letter word"
  if (msg.includes('letter word') && wordLength === 0) {
    const m = msg.match(/(\d+)-letter word/);
    if (m) buildGrid(parseInt(m[1]));
  }

  // detect total guesses "You have N attempts"
  const attM = msg.match(/You have (\d+) attempt/);
  if (attM) totalRows = parseInt(attM[1]);

  // parse "Word:  <state>" line and update grid
  const wordM = msg.match(/Word:\s+([A-Za-z*]+)/);
  if (wordM && wordLength > 0) {
    const state = wordM[1].split('');
    if (state.length === wordLength) {
      currentState = state;
      const row = Math.max(0, currentRow - 1);
      applyState(row, currentState);
    }
  }

  // parse hint counts
  const corM = msg.match(/(\d+) correct position/);
  if (corM) hintCorrect.textContent = `✅  ${corM[1]} correct`;

  const wroM = msg.match(/(\d+) right letter, wrong spot/);
  if (wroM) hintWrong.textContent = `🔄  ${wroM[1]} wrong spot`;

  const remM = msg.match(/(\d+) guess/);
  if (remM && msg.includes('remaining')) hintRemain.textContent = msg.trim();

  // win / loss
  if (msg.includes('Correct!') || msg.includes('guessed')) {
    endGame(true, msg);
  }
  if (msg.includes('Out of guesses') || msg.includes('survived')) {
    endGame(false, msg);
  }
  if (msg.includes('Game over')) {
    setInputEnabled(false);
  }
}

// ── input / send ───────────────────────────────────────────────────────────

function setInputEnabled(on) {
  answerInput.disabled = !on;
  sendBtn.disabled     = !on;
  if (!on) promptLabel.textContent = 'Waiting…';
}

async function submitAnswer() {
  if (answerInput.disabled) return;
  const val = answerInput.value.trim();
  if (!val) return;

  // if guesser, paint the row immediately for snappy feel
  if (role === 'guesser' && wordLength > 0) {
    const guess = val.toLowerCase();
    if (guess.length === wordLength && /^[a-z]+$/.test(guess)) {
      paintGuessRow(currentRow, guess);
      currentRow++;
    }
  }

  answerInput.value = '';
  setInputEnabled(false);

  await fetch('/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer: val })
  });
}

sendBtn.addEventListener('click', submitAnswer);
answerInput.addEventListener('keydown', e => { if (e.key === 'Enter') submitAnswer(); });

// ── end-game ───────────────────────────────────────────────────────────────

function endGame(won, msg) {
  gameOver = true;
  setInputEnabled(false);
  const colour = won ? 'var(--green)' : 'var(--red)';
  const label  = won ? '🎉 YOU WON'    : '💀 GAME OVER';
  roleBadge.textContent = label;
  roleBadge.style.color = colour;
  hintRemain.textContent = '';
  hintCorrect.style.color = colour;
}

// ── log helper ─────────────────────────────────────────────────────────────

function addLog(text, cls) {
  const line = document.createElement('div');
  line.className   = cls || 'log-msg';
  line.textContent = text;
  logEl.appendChild(line);
  logEl.scrollTop = logEl.scrollHeight;
}
</script>
</body>
</html>
"""

# ── main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # start the TCP → game-server thread before Flask begins serving
    t = threading.Thread(target=tcp_thread, daemon=True)
    t.start()

    # give the TCP thread a moment to attempt connection before first request
    time.sleep(0.3)

    # run Flask on all interfaces so Codespaces port-forwarding works
    # debug=False keeps the reloader off so we don't spawn duplicate TCP threads
    print("Flask client running on http://0.0.0.0:5000")
    print("Open the Codespaces forwarded URL for port 5000 in your browser.")
    app.run(host="0.0.0.0", port=5000, debug=False)





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
