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
#inputBar{width:100%;max-width:500px;padding:8px 16px 12px;flex-shrink:0;
          display:none;gap:8px;align-items:center}
#inputField{flex:1;padding:10px 14px;font-size:1rem;font-family:inherit;font-weight:700;
            border:2px solid var(--border-f);border-radius:4px;outline:none;
            text-transform:uppercase;letter-spacing:.1em}
#inputField:focus{border-color:var(--fg)}
#inputBtn{padding:10px 20px;background:var(--fg);color:#fff;border:none;border-radius:4px;
          font-family:inherit;font-size:.9rem;font-weight:700;cursor:pointer}
#inputBtn:hover{opacity:.85}
</style>
</head>
<body>

<div id="header">
  <div id="title">Worduel</div>
  <div id="rolePill">Connecting…</div>
</div>
<div id="toastBox"></div>
<div id="boardArea"><div id="board"></div></div>
<div id="keyboard"></div>
<div id="inputBar">
  <input id="inputField" type="text" placeholder="Type here…"
         autocomplete="off" spellcheck="false" maxlength="20"/>
  <button id="inputBtn">Send</button>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────────
let role='', wordLength=0, maxGuesses=10;
let currentRow=0, currentCol=0;
let currentGuess=[], pendingGuess=[];
let gameOver=false;
let tiles=[], keyStates={};

// ── Board builder ───────────────────────────────────────────────────────────
function buildBoard(n){
  wordLength=n;
  // scale tile size so the full board fits within the available viewport height
  const availH=window.innerHeight-56-(role==='guesser'?206:32);
  const tileH=Math.min(62,Math.floor((availH-(maxGuesses-1)*5)/maxGuesses));
  const tileW=Math.min(62,Math.floor((Math.min(window.innerWidth,500)-32-(n-1)*5)/n));
  const sz=Math.max(32,Math.min(tileH,tileW));
  document.documentElement.style.setProperty('--tile',sz+'px');
  const board=document.getElementById('board');
  board.innerHTML='';
  tiles=[];
  for(let r=0;r<maxGuesses;r++){
    const row=document.createElement('div');
    row.className='tile-row';
    tiles[r]=[];
    for(let c=0;c<n;c++){
      const tile=document.createElement('div');
      tile.className='tile';
      row.appendChild(tile);
      tiles[r][c]=tile;
    }
    board.appendChild(row);
  }
}

// ── Keyboard builder (guesser only) ────────────────────────────────────────
function buildKeyboard(){
  const rows=[
    ['q','w','e','r','t','y','u','i','o','p'],
    ['a','s','d','f','g','h','j','k','l'],
    ['Enter','z','x','c','v','b','n','m','⌫']
  ];
  const kb=document.getElementById('keyboard');
  kb.innerHTML='';
  rows.forEach(row=>{
    const div=document.createElement('div');
    div.className='key-row';
    row.forEach(k=>{
      const btn=document.createElement('button');
      btn.className='key'+(k.length>1?' wide':'');
      btn.textContent=k.toUpperCase();
      btn.dataset.key=k.toLowerCase();
      btn.addEventListener('click',()=>{
        if(k==='Enter')submitGuess();
        else if(k==='⌫')deleteLetter();
        else addLetter(k);
      });
      div.appendChild(btn);
    });
    kb.appendChild(div);
  });
}

// ── Letter input ────────────────────────────────────────────────────────────
function addLetter(l){
  if(gameOver||role!=='guesser'||currentCol>=wordLength)return;
  const t=tiles[currentRow][currentCol];
  t.textContent=l.toUpperCase(); t.dataset.state='tbd';
  currentGuess.push(l.toLowerCase()); currentCol++;
}

function deleteLetter(){
  if(gameOver||role!=='guesser'||currentCol===0)return;
  currentCol--; currentGuess.pop();
  const t=tiles[currentRow][currentCol];
  t.textContent=''; delete t.dataset.state;
}

function submitGuess(){
  if(gameOver||role!=='guesser')return;
  if(currentCol<wordLength){shakeRow(currentRow);showToast('Not enough letters');return;}
  pendingGuess=[...currentGuess];   // ✅ FIX: save letters before clearing so revealRow can use them
  currentGuess=[]; currentCol=0;
  fetch('/send',{method:'POST',headers:{'Content-Type':'application/json'},
                 body:JSON.stringify({answer:pendingGuess.join('')})});
}

// ── Tile reveal animation ───────────────────────────────────────────────────
function revealRow(row,guess,feedback){
  for(let i=0;i<wordLength;i++){
    const tile=tiles[row][i];
    tile.textContent=(guess[i]||'').toUpperCase();
    const state=feedback[i]||'absent';
    (function(t,s,delay){
      setTimeout(()=>{
        t.style.transition='transform 0.25s ease';
        t.style.transform='rotateX(-90deg)';
        setTimeout(()=>{
          t.dataset.state=s;
          t.style.transform='rotateX(0)';
          if(guess[i])updateKeyState(guess[i],s);
        },250);
      },delay);
    })(tile,state,i*350);
  }
}

function updateKeyState(letter,state){
  const l=letter.toLowerCase();
  const priority={correct:3,present:2,absent:1};
  if((priority[state]||0)>(priority[keyStates[l]]||0)){
    keyStates[l]=state;
    const btn=document.querySelector(`[data-key="${l}"]`);
    if(btn)btn.dataset.state=state;
  }
}

// ── Row animations ──────────────────────────────────────────────────────────
function shakeRow(row){
  if(!tiles[row])return;
  tiles[row].forEach(t=>{
    t.style.animation='none'; void t.offsetWidth;   // force reflow so re-applying shake works
    t.style.animation='shake 0.5s ease';
    setTimeout(()=>{t.style.animation='';},500);
  });
}

function bounceRow(row){
  if(!tiles[row])return;
  tiles[row].forEach((t,i)=>setTimeout(()=>{
    t.style.animation='bounce 1s ease';
    setTimeout(()=>{t.style.animation='';},1000);
  },i*100));
}

// ── Toast notifications ─────────────────────────────────────────────────────
function showToast(msg,cls=''){
  const box=document.getElementById('toastBox');
  const t=document.createElement('div');
  t.className='toast'+(cls?' '+cls:'');
  t.textContent=msg;
  box.appendChild(t);
  setTimeout(()=>t.remove(),2800);
}

// ── Role pill ───────────────────────────────────────────────────────────────
function setRolePill(cls,text){
  const p=document.getElementById('rolePill');
  p.className=cls;
  if(text!==undefined)p.textContent=text;
}

// ── Protocol message handler ────────────────────────────────────────────────
// lines the server sends that the board already shows visually — suppress toasts for these
const SILENT=[
  /^\s*$/,/^Word:\s+/,/^Feedback:\s+/,/^\s+\d+ correct/,
  /^\s+\d+ right letter/,/^\s+\d+ guess/,/^===\s*WORDUEL/,
  /^You are Player/,/^\s+Guess \d+:/,/^→\s+state:/,
];

function handleMsg(msg){
  // ── structured protocol messages ───────────────────────────────────────
  if(msg.startsWith('ROLE:')){
    role=msg.slice(5);
    if(role==='setter'){
      setRolePill('setter','Wordsetter');
    }else{
      setRolePill('guesser','Guesser');
    }
    return;
  }

  if(msg.startsWith('WORDLEN:')){
    buildBoard(parseInt(msg.slice(8)));
    if(role==='guesser')buildKeyboard();
    return;
  }

  if(msg.startsWith('FEEDBACK:')){
    // guesser: color the row they just submitted using the saved pendingGuess
    const feedback=msg.slice(9).split(',');
    revealRow(currentRow,pendingGuess,feedback);
    pendingGuess=[];
    currentRow++;
    return;
  }

  if(msg.startsWith('SPECTATE:')){
    // setter: show the guesser's attempt on the spectator board
    const rest=msg.slice(9);
    const spIdx=rest.indexOf(' ');
    const guess=rest.slice(0,spIdx).toLowerCase().split('');
    const feedback=rest.slice(spIdx+1).split(',');
    revealRow(currentRow,guess,feedback);
    currentRow++;
    return;
  }

  if(msg.startsWith('WIN:')){
    const parts=msg.slice(4).split(' ');
    const word=parts[0], attempts=parts[1];
    gameOver=true;
    if(role==='guesser'){
      setTimeout(()=>bounceRow(currentRow-1),wordLength*350+100);
      showToast(word,'win');
      setRolePill('won','You Won!');
    }else{
      showToast(`Guessed in ${attempts}!`,'win');
      setRolePill('won','Guesser Won');
    }
    return;
  }

  if(msg.startsWith('LOSE:')){
    const word=msg.slice(5);
    gameOver=true;
    showToast(word,'');
    setRolePill('lost',role==='setter'?'You Win!':'Game Over');
    return;
  }

  // plain-text fall-through: show brief toast for non-verbose lines
  if(msg.trim()&&!SILENT.some(re=>re.test(msg))){
    showToast(msg.trim().slice(0,80));
  }
}

// ── Input bar (setter word entry and re-validation prompts) ─────────────────
function handleInputRequest(prompt){
  // guesser uses the board keyboard; setter uses the text input bar
  if(role!=='guesser'){
    const bar=document.getElementById('inputBar');
    const field=document.getElementById('inputField');
    field.placeholder=prompt||'Type here…';
    bar.style.display='flex';
    field.focus();
  }
}

function sendInput(){
  const field=document.getElementById('inputField');
  const val=field.value.trim();
  if(!val)return;
  field.value='';
  document.getElementById('inputBar').style.display='none';
  fetch('/send',{method:'POST',headers:{'Content-Type':'application/json'},
                 body:JSON.stringify({answer:val})});
}

document.getElementById('inputBtn').addEventListener('click',sendInput);
document.getElementById('inputField').addEventListener('keydown',e=>{
  if(e.key==='Enter')sendInput();
});

// ── Physical keyboard for guesser ───────────────────────────────────────────
document.addEventListener('keydown',e=>{
  if(role!=='guesser'||gameOver||wordLength===0)return;
  if(e.ctrlKey||e.altKey||e.metaKey)return;
  if(e.key==='Enter')submitGuess();
  else if(e.key==='Backspace')deleteLetter();
  else if(/^[a-zA-Z]$/.test(e.key))addLetter(e.key);
});

// ── SSE connection ───────────────────────────────────────────────────────────
const es=new EventSource('/stream');
es.addEventListener('msg',e=>handleMsg(e.data));
es.addEventListener('input_request',e=>handleInputRequest(e.data));
es.addEventListener('error',()=>showToast('Connection lost…'));
</script>

</body>
</html>"""


if __name__ == "__main__":
    threading.Thread(target=tcp_thread, daemon=True).start()
    time.sleep(0.3)
    print("Worduel web client  ->  http://0.0.0.0:5001")
    app.run(host="0.0.0.0", port=5001, debug=False)
