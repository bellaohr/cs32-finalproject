"""
WORDUEL — pygame GUI
A Wordle-style word guessing game.
Run with:  python3 worduel_gui.py
"""

import pygame
import random
import math
import sys

pygame.init()

# ── Window ────────────────────────────────────────────────────────────────────
W, H = 520, 720
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("WORDUEL")
clock = pygame.time.Clock()

# ── Palette (dark ink + warm gold + green/amber/red tile scheme) ──────────────
BG          = (18,  18,  20)
TILE_EMPTY  = (30,  30,  35)
TILE_BORDER = (58,  58,  65)
TILE_FILLED = (40,  40,  48)
COL_CORRECT = ( 83, 141,  78)   # green  – right letter, right spot
COL_PRESENT = (181, 159,  59)   # amber  – right letter, wrong spot
COL_ABSENT  = ( 58,  58,  65)   # grey   – not in word
KEY_DEFAULT = ( 52,  52,  60)
WHITE       = (255, 255, 255)
OFF_WHITE   = (215, 214, 208)
GOLD        = (212, 175,  55)
SOFT_RED    = (186,  74,  74)

# ── Fonts ─────────────────────────────────────────────────────────────────────
F_TITLE  = pygame.font.SysFont("Georgia",      30, bold=True)
F_TILE   = pygame.font.SysFont("Georgia",      34, bold=True)
F_KEY    = pygame.font.SysFont("Trebuchet MS", 15, bold=True)
F_MSG    = pygame.font.SysFont("Trebuchet MS", 20, bold=True)
F_SMALL  = pygame.font.SysFont("Trebuchet MS", 14)

# ── Dictionary (100 words, 4–6 letters) ───────────────────────────────────────
DICTIONARY = [
    "apple","brave","crane","daisy","eagle",
    "fable","globe","haven","ivory","joker",
    "knack","lemon","maple","noble","ocean",
    "piano","quill","raven","stone","tiger",
    "umbra","vivid","waltz","xenon","yacht",
    "zebra","amber","blaze","cinch","drape",
    "ember","flint","gravel","hinge","inlet",
    "jumpy","karma","lunar","mirth","nerve",
    "optic","plumb","quirk","rivet","swamp",
    "thorn","ultra","vapor","whelp","xylem",
    "yearn","zonal","acorn","bison","cloak",
    "depot","envoy","frond","groan","hyena",
    "igloo","joust","knelt","llama","mocha",
    "notch","onset","pixel","qualm","rhino",
    "scone","trout","unzip","venom","whirl",
    "expel","yodel","zesty","algae","borax",
    "cyber","denim","epoch","fluke","guava",
    "hutch","icily","jingo","khaki","libel",
    "maxim","nymph","olive","prism","query",
    "rabbi","scald","talon","undue","voila",
]

MAX_GUESSES = 6

# ── Grid layout ───────────────────────────────────────────────────────────────
TILE_SIZE = 58
TILE_GAP  = 6

def grid_origin(word_len):
    total_w = word_len * TILE_SIZE + (word_len - 1) * TILE_GAP
    ox = (W - total_w) // 2
    oy = 90
    return ox, oy

# ── On-screen keyboard rows ───────────────────────────────────────────────────
KB_ROWS = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
KEY_W, KEY_H, KEY_GAP = 36, 42, 5

def kb_row_x(row_str):
    total = len(row_str) * KEY_W + (len(row_str) - 1) * KEY_GAP
    return (W - total) // 2

KB_Y = [H - 180, H - 180 + KEY_H + KEY_GAP, H - 180 + 2*(KEY_H + KEY_GAP)]

# ── Game state ────────────────────────────────────────────────────────────────
def new_game():
    secret = random.choice(DICTIONARY)
    return {
        "secret":   secret,
        "length":   len(secret),
        "guesses":  [],           # list of (guess_str, result_list)
        "current":  "",           # letters typed so far
        "phase":    "playing",    # playing | won | lost
        "message":  "",
        "msg_timer": 0,
        "key_colors": {},         # letter -> color constant
        "shake":    False,
        "shake_t":  0,
        "flip_row": -1,           # row currently flipping
        "flip_t":   0,
        "flip_done": False,
    }

state = new_game()

# ── Logic ─────────────────────────────────────────────────────────────────────
def evaluate(secret, guess):
    """Return list of 'correct'|'present'|'absent' for each letter."""
    result      = ["absent"] * len(guess)
    secret_used = [False] * len(secret)
    guess_used  = [False] * len(guess)

    for i in range(len(guess)):
        if guess[i] == secret[i]:
            result[i]      = "correct"
            secret_used[i] = True
            guess_used[i]  = True

    for i in range(len(guess)):
        if guess_used[i]:
            continue
        for j in range(len(secret)):
            if not secret_used[j] and guess[i] == secret[j]:
                result[i]      = "present"
                secret_used[j] = True
                break

    return result

COLOR_MAP = {"correct": COL_CORRECT, "present": COL_PRESENT, "absent": COL_ABSENT}

def submit_guess(st):
    guess = st["current"].lower()
    if len(guess) != st["length"]:
        st["message"]   = f"Need {st['length']} letters!"
        st["msg_timer"] = 90
        st["shake"]     = True
        st["shake_t"]   = 0
        return

    result = evaluate(st["secret"], guess)
    st["guesses"].append((guess, result))
    st["current"] = ""

    # update keyboard colours (only upgrade: absent→present→correct)
    priority = {"correct": 2, "present": 1, "absent": 0}
    for letter, res in zip(guess, result):
        col = COLOR_MAP[res]
        if letter not in st["key_colors"]:
            st["key_colors"][letter] = col
        else:
            cur = st["key_colors"][letter]
            cur_p = max((priority[k] for k, v in COLOR_MAP.items() if v == cur), default=0)
            new_p = priority[res]
            if new_p > cur_p:
                st["key_colors"][letter] = col

    # start flip animation for the row just submitted
    st["flip_row"]  = len(st["guesses"]) - 1
    st["flip_t"]    = 0
    st["flip_done"] = False

    if guess == st["secret"]:
        st["phase"]     = "won"
        st["message"]   = "Brilliant! 🎉"
        st["msg_timer"] = 200
    elif len(st["guesses"]) >= MAX_GUESSES:
        st["phase"]     = "lost"
        st["message"]   = f"The word was {st['secret'].upper()}"
        st["msg_timer"] = 300

# ── Drawing helpers ───────────────────────────────────────────────────────────
def draw_rounded(surf, color, rect, r=6):
    pygame.draw.rect(surf, color, rect, border_radius=r)

def blit_centered(surf, img, cx, cy):
    surf.blit(img, (cx - img.get_width()//2, cy - img.get_height()//2))

def draw_tile(surf, letter, col_bg, col_border, cx, cy, scale_y=1.0):
    """Draw one tile, optionally y-squished for flip animation."""
    tw = TILE_SIZE - 2
    th = int((TILE_SIZE - 2) * scale_y)
    rect = pygame.Rect(cx - tw//2, cy - th//2, tw, th)
    draw_rounded(surf, col_bg, rect, r=4)
    pygame.draw.rect(surf, col_border, rect, 2, border_radius=4)
    if letter and th > 10:
        t = F_TILE.render(letter.upper(), True, WHITE)
        blit_centered(surf, t, cx, cy)

# ── Main draw ─────────────────────────────────────────────────────────────────
def draw(st):
    screen.fill(BG)

    # title
    title = F_TITLE.render("W O R D U E L", True, GOLD)
    screen.blit(title, (W//2 - title.get_width()//2, 14))
    pygame.draw.line(screen, (50, 50, 58), (30, 56), (W-30, 56), 1)

    ox, oy = grid_origin(st["length"])
    shake_dx = 0
    if st["shake"]:
        shake_dx = int(6 * math.sin(st["shake_t"] * 1.5))

    # ── grid rows ─────────────────────────────────────────────────────────────
    for row in range(MAX_GUESSES):
        for col in range(st["length"]):
            cx = ox + col * (TILE_SIZE + TILE_GAP) + TILE_SIZE // 2
            cy = oy + row * (TILE_SIZE + TILE_GAP) + TILE_SIZE // 2

            # shake only the active row
            active_row = len(st["guesses"])
            if row == active_row and st["shake"]:
                cx += shake_dx

            if row < len(st["guesses"]):
                guess, result = st["guesses"][row]
                letter = guess[col] if col < len(guess) else ""
                res    = result[col]
                bg     = COLOR_MAP[res]
                border = bg

                # flip animation
                if row == st["flip_row"] and not st["flip_done"]:
                    flip_progress = min(st["flip_t"] / 40, 1.0)   # 0→1 over 40 frames
                    col_progress  = col / st["length"]
                    local_t       = flip_progress - col_progress * 0.3
                    local_t       = max(0, min(local_t, 1))
                    # first half: scale down, second half: scale up with new color
                    if local_t < 0.5:
                        scale_y = 1.0 - local_t * 2
                        draw_tile(screen, letter, TILE_FILLED, TILE_BORDER, cx, cy, scale_y)
                    else:
                        scale_y = (local_t - 0.5) * 2
                        draw_tile(screen, letter, bg, border, cx, cy, scale_y)
                else:
                    draw_tile(screen, letter, bg, border, cx, cy)

            elif row == len(st["guesses"]) and st["phase"] == "playing":
                # current typing row
                letter = st["current"][col] if col < len(st["current"]) else ""
                bg     = TILE_FILLED if letter else TILE_EMPTY
                border = OFF_WHITE   if letter else TILE_BORDER
                cx_off = cx + shake_dx if st["shake"] else cx
                draw_tile(screen, letter, bg, border, cx_off, cy)
            else:
                draw_tile(screen, "", TILE_EMPTY, TILE_BORDER, cx, cy)

    # ── on-screen keyboard ────────────────────────────────────────────────────
    for r, row_str in enumerate(KB_ROWS):
        rx = kb_row_x(row_str)
        for c, ch in enumerate(row_str):
            kx = rx + c * (KEY_W + KEY_GAP)
            ky = KB_Y[r]
            kl = ch.lower()
            bg = st["key_colors"].get(kl, KEY_DEFAULT)
            draw_rounded(screen, bg, pygame.Rect(kx, ky, KEY_W, KEY_H), r=4)
            kt = F_KEY.render(ch, True, WHITE)
            screen.blit(kt, (kx + KEY_W//2 - kt.get_width()//2,
                             ky + KEY_H//2 - kt.get_height()//2))

    # ENTER / DEL keys
    enter_rect = pygame.Rect(kb_row_x("ZXCVBNM") - 52, KB_Y[2], 48, KEY_H)
    del_rect   = pygame.Rect(kb_row_x("ZXCVBNM") + 7*(KEY_W+KEY_GAP) + 4, KB_Y[2], 44, KEY_H)
    draw_rounded(screen, KEY_DEFAULT, enter_rect, r=4)
    draw_rounded(screen, KEY_DEFAULT, del_rect,   r=4)
    et = F_SMALL.render("ENTER", True, WHITE)
    dt = F_SMALL.render("DEL",   True, WHITE)
    screen.blit(et, (enter_rect.centerx - et.get_width()//2, enter_rect.centery - et.get_height()//2))
    screen.blit(dt, (del_rect.centerx   - dt.get_width()//2, del_rect.centery   - dt.get_height()//2))

    # ── message banner ────────────────────────────────────────────────────────
    if st["msg_timer"] > 0 and st["message"]:
        alpha = min(255, st["msg_timer"] * 4)
        msg_s = F_MSG.render(st["message"], True, BG)
        pill_w = msg_s.get_width() + 28
        pill_h = msg_s.get_height() + 14
        pill   = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pygame.draw.rect(pill, (*WHITE, alpha), (0, 0, pill_w, pill_h), border_radius=8)
        pill.blit(msg_s, (14, 7))
        screen.blit(pill, (W//2 - pill_w//2, 62))

    # ── play again hint ───────────────────────────────────────────────────────
    if st["phase"] in ("won", "lost"):
        hint = F_SMALL.render("Press  R  to play again", True, (100, 100, 110))
        screen.blit(hint, (W//2 - hint.get_width()//2, H - 28))

    pygame.display.flip()

# ── Main loop ─────────────────────────────────────────────────────────────────
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            st = state

            if event.key == pygame.K_ESCAPE:
                running = False

            elif event.key == pygame.K_r and st["phase"] in ("won", "lost"):
                state = new_game()

            elif st["phase"] == "playing":
                if event.key == pygame.K_RETURN:
                    submit_guess(st)

                elif event.key == pygame.K_BACKSPACE:
                    st["current"] = st["current"][:-1]

                elif event.unicode.isalpha() and len(st["current"]) < st["length"]:
                    st["current"] += event.unicode.lower()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            st = state
            if st["phase"] == "playing":
                # on-screen keyboard click
                for r, row_str in enumerate(KB_ROWS):
                    rx = kb_row_x(row_str)
                    for c, ch in enumerate(row_str):
                        kx = rx + c * (KEY_W + KEY_GAP)
                        ky = KB_Y[r]
                        if pygame.Rect(kx, ky, KEY_W, KEY_H).collidepoint(mx, my):
                            if len(st["current"]) < st["length"]:
                                st["current"] += ch.lower()

                enter_rect = pygame.Rect(kb_row_x("ZXCVBNM") - 52, KB_Y[2], 48, KEY_H)
                del_rect   = pygame.Rect(kb_row_x("ZXCVBNM") + 7*(KEY_W+KEY_GAP) + 4, KB_Y[2], 44, KEY_H)
                if enter_rect.collidepoint(mx, my):
                    submit_guess(st)
                if del_rect.collidepoint(mx, my):
                    st["current"] = st["current"][:-1]

    # ── animate ───────────────────────────────────────────────────────────────
    st = state
    if st["shake"]:
        st["shake_t"] += 1
        if st["shake_t"] > 20:
            st["shake"]   = False
            st["shake_t"] = 0

    if st["flip_row"] >= 0 and not st["flip_done"]:
        st["flip_t"] += 1
        if st["flip_t"] > 60:
            st["flip_done"] = True

    if st["msg_timer"] > 0:
        st["msg_timer"] -= 1

    draw(state)
    clock.tick(60)

pygame.quit()
sys.exit()
