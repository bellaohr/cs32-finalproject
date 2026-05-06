"""
client_web.py  -  NYT Wordle-style Flask web interface for Worduel
===================================================================
Run instead of client.py. server.py is unchanged.

Usage
-----
    pip install flask
    python client_web.py           # Player 1  -> port 5000
    # edit last line: port=5001    # Player 2  -> port 5001
"""

import socket
import threading
import queue
import time
from flask import Flask, Response, request, jsonify, render_template_string

HOST = "127.0.0.1"
PORT = 65434

app = Flask(__name__)

event_queue:    queue.Queue = queue.Queue()
pending_answer: queue.Queue = queue.Queue()

sock:           socket.socket | None = None
connected:      bool = False
connect_error:  str | None = None
pending_prompt: str | None = None


def push(event_type: str, data: str):
    event_queue.put({"type": event_type, "data": data})


def tcp_thread():
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
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if line.startswith("INPUT:"):
                    prompt = line[len("INPUT:"):]
                    pending_prompt = prompt
                    push("input_request", prompt)
                    answer = pending_answer.get()
                    pending_prompt = None
                    sock.sendall((answer + "\n").encode())
                    push("sent", answer)
                else:
                    push("msg", line)
    except ConnectionRefusedError:
        connect_error = f"Could not connect to {HOST}:{PORT}. Is server.py running?"
        push("error", connect_error)
    except Exception as exc:
        push("error", str(exc))


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/stream")
def stream():
    def generate():
        while True:
            try:
                evt = event_queue.get(timeout=30)
                yield f"event: {evt['type']}\ndata: {evt['data']}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"
    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/send", methods=["POST"])
def send():
    data   = request.get_json()
    answer = (data or {}).get("answer", "").strip()
    if answer:
        pending_answer.put(answer)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "empty"}), 400


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Worduel</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@700;900&display=swap');
:root {
  --correct:#6aaa64; --present:#c9b458; --absent:#787c7e;
  --border-e:#d3d6da; --border-f:#878a8c;
  --key-bg:#d3d6da; --fg:#1a1a1b; --bg:#ffffff; --tile:62px; --gap:5px;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--fg);font-family:'Libre Franklin','Helvetica Neue',Arial,sans-serif;
     display:flex;flex-direction:column;align-items:center;height:100vh;overflow:hidden;user-select:none}
#header{width:100%;max-width:500px;height:56px;display:flex;align-items:center;
        justify-content:space-between;border-bottom:1px solid var(--border-e);
        padding:0 16px;flex-shrink:0;position:relative}
#title{position:absolute;left:50%;transform:translateX(-50%);font-weight:900;
       font-size:1.75rem;letter-spacing:.04em}
#rolePill{font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
          padding:4px 10px;border-radius:20px;background:#edeff1;color:var(--absent);transition:all .3s;white-space:nowrap}
#rolePill.setter{background:#fff3cd;color:#856404}
#rolePill.guesser{background:#d1e7dd;color:#0a3622}
#rolePill.won{background:var(--correct);color:#fff}
#rolePill.lost{background:var(--absent);color:#fff}
#toastBox{position:fixed;top:66px;left:50%;transform:translateX(-50%);
          display:flex;flex-direction:column;align-items:center;gap:8px;z-index:200;pointer-events:none}
.toast{background:var(--fg);color:#fff;font-size:.82rem;font-weight:700;padding:10px 18px;
       border-radius:4px;white-space:nowrap;animation:tIn .15s ease,tOut .3s ease 2.5s forwards}
.toast.win{background:var(--correct)}
@keyframes tIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}
@keyframes tOut{to{opacity:0}}
#boardArea{flex:1;display:flex;align-items:center;justify-content:center;padding:10px 0;overflow:hidden}
#board{display:flex;flex-direction:column;gap:var(--gap)}
.tile-row{display:flex;gap:var(--gap)}
.tile{width:var(--tile);height:var(--tile);border:2px solid var(--border-e);
      display:flex;align-items:center;justify-content:center;
      font-size:2rem;font-weight:900;text-transform:uppercase;color:var(--fg);background:var(--bg);
      transition:border-color .05s}
.tile[data-state="tbd"]{border-color:var(--border-f);animation:tilePop .1s ease}
@keyframes tilePop{0%,100%{transform:scale(1)}50%{transform:scale(1.1)}}
.tile[data-state="correct"],.tile[data-state="present"],.tile[data-state="absent"]{color:#fff;border-color:transparent}
.tile[data-state="correct"]{background:var(--correct)}
.tile[data-state="present"]{background:var(--present)}
.tile[data-state="absent"]{background:var(--absent)}
.tile.flip{animation:flipIn .5s ease forwards}
@keyframes flipIn{0%{transform:rotateX(0)}49%{transform:rotateX(-90deg)}50%{transform:rotateX(-90deg)}100%{transform:rotateX(0)}}
@keyframes shake{0%,100%{transform:translateX(0)}20%,60%{transform:translateX(-4px)}40%,80%{transform:translateX(4px)}}
@keyframes bounce{0%,20%{transform:translateY(0)}40%{transform:translateY(-20px)}50%{transform:translateY(0)}60%{transform:translateY(-12px)}80%,100%{transform:translateY(0)}}
#keyboard{width:100%;max-width:500px;padding:0 8px 12px;flex-shrink:0}
.key-row{display:flex;justify-content:center;gap:6px;margin-bottom:8px}
.key{height:58px;min-width:43px;max-width:43px;flex:1;border-radius:4px;border:none;
     background:var(--key-bg);color:var(--fg);font-family:inherit;font-size:.85rem;font-weight:700;
     text-transform:uppercase;cursor:pointer;display:flex;align-items:center;justify-content:center;
     transition:background .2s,color .2s;-webkit-tap-highlight-color:transparent}
.key.wide{max-width:65px;font-size:.72rem}
.key[data-state="correct"]{background:var(--correct);color:#fff}
.key[data-state="present"]{background:var(--present);color:#fff}
.key[data-state="absent"]{background:var(--absent);color:#fff}
</style>
</head>
<body>

<script>
let role='',wordLength=0,maxGuesses=10,currentRow=0,currentCol=0;
let currentGuess=[],gameOver=false;
let tiles=[],keyStates={};
let lastGuess='',lastCorrect=0,lastPresent=0;

function addLetter(l){
  if(gameOver||role!=='guesser'||currentCol>=wordLength)return;
  const t=tiles[currentRow][currentCol];
  t.textContent=l.toUpperCase(); t.dataset.state='tbd';
  currentGuess.push(l.toLowerCase()); currentCol++;
}

function deleteLetter(){
  if(gameOver||role!=='guesser'||currentCol===0)return;
  currentCol--; currentGuess.pop();
  tiles[currentRow][currentCol].textContent='';
}

function submitGuess(){
  if(gameOver||role!=='guesser')return;
  if(currentCol<wordLength){shakeRow(currentRow);showToast('Not enough letters');return;}
  fetch('/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answer:currentGuess.join('')})});
}

function handleMsg(msg){
  currentGuess = []; currentCol = 0;   // ✅ FIX: unlock input every server response

  const sm = msg.match(/Word:\s+([A-Za-z*]+)/);
  const fm = msg.match(/Feedback:\s+(.+)/);

  if(sm && fm && role==='guesser'){
    revealRow(currentRow, currentGuess.join(''), fm[1], lastCorrect, lastPresent);
    currentRow++;
  }
}

const es=new EventSource('/stream');
es.addEventListener('msg',e=>handleMsg(e.data));
es.addEventListener('input_request',()=>role='guesser');

</script>

</body>
</html>"""


if __name__ == "__main__":
    threading.Thread(target=tcp_thread, daemon=True).start()
    time.sleep(0.3)
    print("Worduel web client  ->  http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5001, debug=False)
