"""
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

# server connection configuration
HOST = "127.0.0.1"
PORT = 65434

# flask app
app = Flask(__name__)

event_queue:    queue.Queue = queue.Queue()
pending_answer: queue.Queue = queue.Queue()

# global connection state
sock:           socket.socket | None = None
connected:      bool = False
connect_error:  str | None = None
pending_prompt: str | None = None

# pushing events to browser via event stream
def push(event_type: str, data: str):
    event_queue.put({"type": event_type, "data": data})

# background tcp client thread -- like basically socket connection
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
        # if server isn't running
        connect_error = f"Could not connect to {HOST}:{PORT}. Is server.py running?"
        push("error", connect_error)

    except Exception as exc:
        # if its an unexpected error
        push("error", str(exc))

# FLASK ROUTES!
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

# HTML + CSS + JavaScrpt
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
#setterPanel{width:100%;max-width:500px;padding:16px;display:none;
             flex-direction:column;align-items:center;gap:12px;flex-shrink:0}
#setterPanel p{font-size:.85rem;color:var(--absent);text-align:center;line-height:1.5;font-weight:700}
.setter-row{display:flex;gap:10px;width:100%;max-width:320px}
#setterInput{flex:1;border:2px solid var(--border-e);border-radius:4px;padding:12px 14px;
             font-family:inherit;font-size:1.1rem;font-weight:900;text-transform:uppercase;
             letter-spacing:.1em;outline:none;color:var(--fg);transition:border-color .2s}
#setterInput:focus{border-color:var(--fg)}
#setterBtn{padding:12px 20px;border:none;border-radius:4px;background:var(--fg);color:#fff;
           font-family:inherit;font-size:.8rem;font-weight:900;letter-spacing:.08em;
           text-transform:uppercase;cursor:pointer;transition:opacity .2s}
#setterBtn:hover{opacity:.75}
#setterBtn:disabled{opacity:.3;cursor:not-allowed}
#waitOverlay{position:fixed;inset:0;background:rgba(255,255,255,.93);
             display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px;z-index:100}
#waitOverlay h2{font-size:1.6rem;font-weight:900;letter-spacing:.06em}
#waitMsg{font-size:.85rem;color:var(--absent);text-align:center;max-width:300px;line-height:1.7;font-weight:700}
.dots span{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--border-e);
           margin:0 3px;animation:dp 1.2s infinite}
.dots span:nth-child(2){animation-delay:.2s}.dots span:nth-child(3){animation-delay:.4s}
@keyframes dp{0%,80%,100%{transform:scale(.7);opacity:.4}40%{transform:scale(1);opacity:1}}
</style>
</head>
<body>

<div id="waitOverlay">
  <h2>WORDUEL</h2>
  <div class="dots"><span></span><span></span><span></span></div>
  <div id="waitMsg">Connecting to game server…</div>
</div>

<div id="toastBox"></div>

<header id="header">
  <div></div>
  <div id="title">Worduel</div>
  <div id="rolePill">—</div>
</header>

<div id="boardArea"><div id="board"></div></div>

<div id="keyboard">
  <div class="key-row">
    <button class="key" data-key="q">Q</button><button class="key" data-key="w">W</button>
    <button class="key" data-key="e">E</button><button class="key" data-key="r">R</button>
    <button class="key" data-key="t">T</button><button class="key" data-key="y">Y</button>
    <button class="key" data-key="u">U</button><button class="key" data-key="i">I</button>
    <button class="key" data-key="o">O</button><button class="key" data-key="p">P</button>
  </div>
  <div class="key-row">
    <button class="key" data-key="a">A</button><button class="key" data-key="s">S</button>
    <button class="key" data-key="d">D</button><button class="key" data-key="f">F</button>
    <button class="key" data-key="g">G</button><button class="key" data-key="h">H</button>
    <button class="key" data-key="j">J</button><button class="key" data-key="k">K</button>
    <button class="key" data-key="l">L</button>
  </div>
  <div class="key-row">
    <button class="key wide" data-key="Enter">Enter</button>
    <button class="key" data-key="z">Z</button><button class="key" data-key="x">X</button>
    <button class="key" data-key="c">C</button><button class="key" data-key="v">V</button>
    <button class="key" data-key="b">B</button><button class="key" data-key="n">N</button>
    <button class="key" data-key="m">M</button>
    <button class="key wide" data-key="Backspace">&#9003;</button>
  </div>
</div>

<div id="setterPanel">
  <p id="setterPrompt">Enter a 4&#8211;6 letter word for your opponent to guess.</p>
  <div class="setter-row">
    <input id="setterInput" type="text" maxlength="6" placeholder="CRANE" autocomplete="off" spellcheck="false"/>
    <button id="setterBtn">Set &#9654;</button>
  </div>
</div>

<script>
let role='',wordLength=0,maxGuesses=10,currentRow=0,currentCol=0;
let currentGuess=[],gameOver=false,waitingForServer=false;
let tiles=[],keyStates={},lastGuess='',lastCorrect=0,lastPresent=0;

const board=document.getElementById('board'),
      keyboard=document.getElementById('keyboard'),
      setterPanel=document.getElementById('setterPanel'),
      setterInput=document.getElementById('setterInput'),
      setterBtn=document.getElementById('setterBtn'),
      setterProm=document.getElementById('setterPrompt'),
      rolePill=document.getElementById('rolePill'),
      waitOverlay=document.getElementById('waitOverlay'),
      waitMsg=document.getElementById('waitMsg'),
      toastBox=document.getElementById('toastBox');

function buildBoard(wlen,rows){
  wordLength=wlen; maxGuesses=rows; board.innerHTML=''; tiles=[];
  document.documentElement.style.setProperty('--tile',(wlen<=5?62:56)+'px');
  for(let r=0;r<rows;r++){
    const rowEl=document.createElement('div'); rowEl.className='tile-row';
    const rowArr=[];
    for(let c=0;c<wlen;c++){
      const t=document.createElement('div'); t.className='tile';
      rowEl.appendChild(t); rowArr.push(t);
    }
    board.appendChild(rowEl); tiles.push(rowArr);
  }
}

function addLetter(l){
  if(gameOver||waitingForServer||role!=='guesser'||currentCol>=wordLength)return;
  const t=tiles[currentRow][currentCol];
  t.textContent=l.toUpperCase(); t.dataset.state='tbd';
  t.style.animation='none'; t.offsetHeight; t.style.animation='';
  currentGuess.push(l.toLowerCase()); currentCol++;
}
function deleteLetter(){
  if(gameOver||waitingForServer||role!=='guesser'||currentCol===0)return;
  currentCol--; currentGuess.pop();
  const t=tiles[currentRow][currentCol]; t.textContent=''; t.dataset.state='';
}
function submitGuess(){
  if(gameOver||waitingForServer||role!=='guesser')return;
  if(currentCol<wordLength){shakeRow(currentRow);showToast('Not enough letters');return;}
  waitingForServer=true; lastGuess=currentGuess.join('');
  fetch('/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answer:lastGuess})});
}

function revealRow(row,guess,stateStr,correct,present){
  const states=deriveTileStates(guess,stateStr,correct,present);
  states.forEach((state,c)=>{
    setTimeout(()=>{
      const t=tiles[row][c];
      t.dataset.state=state; t.textContent=guess[c].toUpperCase();
      t.classList.add('flip'); t.style.animationDelay='0s';
      setTimeout(()=>t.classList.remove('flip'),500);
    },c*300);
  });
  setTimeout(()=>{
    guess.split('').forEach((letter,c)=>updateKey(letter,states[c]));
  },states.length*300+100);
}

function deriveTileStates(guess,stateStr,correctCount,presentCount){
  const arr=stateStr.split(''), out=Array(guess.length).fill('absent');
  const usedSlot=Array(guess.length).fill(false), usedGuess=Array(guess.length).fill(false);
  for(let i=0;i<guess.length;i++){
    if(arr[i]!=='*'){out[i]='correct';usedSlot[i]=true;usedGuess[i]=true;}
  }
  let budget=presentCount;
  for(let i=0;i<guess.length&&budget>0;i++){
    if(usedGuess[i])continue;
    let found=false;
    for(let j=0;j<guess.length;j++){
      if(!usedSlot[j]&&arr[j]==='*'&&guess[i]===guess[j]&&i!==j){
        out[i]='present';usedSlot[j]=true;usedGuess[i]=true;budget--;found=true;break;
      }
    }
    if(!found&&budget>0){out[i]='present';usedGuess[i]=true;budget--;}
  }
  return out;
}

function updateKey(letter,state){
  const p={correct:3,present:2,absent:1};
  if(!keyStates[letter]||p[state]>p[keyStates[letter]]){
    keyStates[letter]=state;
    const btn=document.querySelector(`.key[data-key="${letter}"]`);
    if(btn)btn.dataset.state=state;
  }
}

function showSetterPanel(prompt){
  keyboard.style.display='none'; setterPanel.style.display='flex';
  setterProm.textContent=prompt||'Enter a 4\u20136 letter word for your opponent to guess.';
  setterInput.disabled=false; setterBtn.disabled=false; setterInput.focus();
}
function submitSetterWord(){
  const val=setterInput.value.trim().toUpperCase();
  if(val.length<4||val.length>6||!/^[A-Z]+$/.test(val)){showToast('Must be 4\u20136 letters only');return;}
  setterInput.disabled=true; setterBtn.disabled=true;
  fetch('/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answer:val})});
}
setterBtn.addEventListener('click',submitSetterWord);
setterInput.addEventListener('keydown',e=>{if(e.key==='Enter')submitSetterWord();});

const es=new EventSource('/stream');
es.addEventListener('status',e=>{
  if(e.data==='connected')waitMsg.textContent='Connected! Waiting for the other player to join\u2026';
  else waitMsg.textContent='Disconnected from server.';
});
es.addEventListener('error',e=>{waitOverlay.style.display='flex';waitMsg.textContent=e.data||'Connection error.';});
es.addEventListener('msg',e=>handleMsg(e.data));
es.addEventListener('input_request',e=>{
  const prompt=e.data.trim();
  if((prompt.toLowerCase().includes('word')||prompt.toLowerCase().includes('letter'))&&role!=='guesser'){
    role='setter'; rolePill.textContent='\uD83D\uDD12 Word Setter'; rolePill.className='setter';
    waitOverlay.style.display='none'; showSetterPanel(prompt);
  } else {
    waitingForServer=false; waitOverlay.style.display='none';
  }
});
es.addEventListener('sent',e=>{
  if(role==='setter'){setterPanel.style.display='none';waitOverlay.style.display='flex';waitMsg.textContent='Word set! Waiting for your opponent to guess\u2026';}
  if(role==='guesser')lastGuess=e.data.toLowerCase();
});

function handleMsg(msg){
  if(msg.includes('Player 1')&&msg.includes('Wordsetter')){role='setter';rolePill.textContent='\uD83D\uDD12 Word Setter';rolePill.className='setter';}
  if(msg.includes('Player 2')&&msg.includes('Guesser')){role='guesser';rolePill.textContent='\uD83D\uDD0D Guesser';rolePill.className='guesser';}
  if(wordLength===0){
    const lm=msg.match(/(\d+)-letter word/),rm=msg.match(/You have (\d+) attempt/);
    if(lm){buildBoard(parseInt(lm[1]),rm?parseInt(rm[1]):10);waitOverlay.style.display='none';}
  }
  const cm=msg.match(/(\d+) correct position/); if(cm)lastCorrect=parseInt(cm[1]);
  const wm=msg.match(/(\d+) right letter, wrong spot/); if(wm)lastPresent=parseInt(wm[1]);
  const sm=msg.match(/Word:\s+([A-Za-z*]+)/);
  if(sm&&wordLength>0&&role==='guesser'){
    const ss=sm[1];
    if(ss.length===wordLength){
      revealRow(currentRow,lastGuess||currentGuess.join(''),ss,lastCorrect,lastPresent);
      currentRow++; currentCol=0; currentGuess=[]; lastCorrect=0; lastPresent=0;
    }
  }
  if(role==='setter'){
    const gm=msg.match(/Guess \d+: ([A-Z]+)/i); if(gm)showToast('Opponent guessed: '+gm[1].toUpperCase());
  }
  if(msg.includes('Correct!')&&msg.includes('You got it')){
    gameOver=true; rolePill.textContent='\uD83C\uDF89 You Won!'; rolePill.className='won';
    setTimeout(()=>{showToast('Brilliant! \uD83C\uDF89',true);bounceRow(currentRow-1);},wordLength*300+400);
  }
  if(msg.includes('word was guessed')||msg.includes('guessed in')){gameOver=true;showToast(msg.trim(),true);}
  if(msg.includes('Out of guesses')){
    gameOver=true; rolePill.textContent='\uD83D\uDC80 Game Over'; rolePill.className='lost';
    const wrd=msg.match(/word was: ([A-Z]+)/i); if(wrd)showToast('The word was '+wrd[1].toUpperCase());
  }
  if(msg.includes('Game over'))waitingForServer=false;
}

document.addEventListener('keydown',e=>{
  if(role!=='guesser'||e.ctrlKey||e.metaKey||e.altKey)return;
  if(e.key==='Enter')submitGuess();
  else if(e.key==='Backspace')deleteLetter();
  else if(/^[a-zA-Z]$/.test(e.key))addLetter(e.key);
});
document.querySelectorAll('.key').forEach(btn=>{
  btn.addEventListener('click',()=>{
    const k=btn.dataset.key;
    if(k==='Enter')submitGuess(); else if(k==='Backspace')deleteLetter(); else addLetter(k);
  });
});

function showToast(msg,win=false){
  const t=document.createElement('div'); t.className='toast'+(win?' win':''); t.textContent=msg;
  toastBox.appendChild(t); setTimeout(()=>t.remove(),2800);
}
function shakeRow(row){
  const re=board.children[row]; if(!re)return;
  re.style.animation='none'; re.offsetHeight; re.style.animation='shake 0.4s ease';
  setTimeout(()=>re.style.animation='',400);
}
function bounceRow(row){
  if(row<0||!tiles[row])return;
  tiles[row].forEach((t,i)=>{
    setTimeout(()=>{t.style.animation='none';t.offsetHeight;t.style.animation='bounce 0.6s ease';setTimeout(()=>t.style.animation='',600);},i*80);
  });
}
</script>
</body>
</html>"""


if __name__ == "__main__":
    threading.Thread(target=tcp_thread, daemon=True).start()
    time.sleep(0.3)
    print("Worduel web client  ->  http://0.0.0.0:5000")
    print("Open the VS Code forwarded port URL in your browser.")
    app.run(host="0.0.0.0", port=5000, debug=False)
