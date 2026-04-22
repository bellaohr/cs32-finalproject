import socket
import time

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


# ── AI guesser ─────────────────────────────────────────────────────────────────

def build_wordlist(length: int) -> list:
    """Load system dictionary filtered to the right length, with fallback."""
    try:
        with open("/usr/share/dict/words") as f:
            words = [w.strip().lower() for w in f if w.strip().isalpha() and len(w.strip()) == length]
        if words:
            return words
    except FileNotFoundError:
        pass

    # Fallback common words for each length
    fallback = [
        "able","acid","also","area","army","away","baby","back","ball","band",
        "bank","base","bath","bear","beat","beer","bell","best","bird","blow",
        "blue","boat","body","bone","book","boom","boot","born","boss","both",
        "burn","calm","came","card","care","case","cash","cast","cave","cell",
        "chip","city","club","coal","coat","code","cold","come","cook","cool",
        "cope","copy","core","corn","cost","crew","crop","cure","dark","data",
        "date","dawn","dead","deal","dear","debt","deep","deny","desk","diet",
        "dire","dirt","dish","disk","dock","done","door","dose","down","draw",
        "drop","drug","drum","dual","dull","dump","dust","duty","each","earn",
        "ease","east","edge","emit","even","ever","evil","face","fact","fail",
        "fair","fall","fame","fare","farm","fast","fate","fear","feed","feel",
        "feet","fell","felt","file","fill","film","find","fine","fire","firm",
        "fish","fist","flag","flat","flew","flip","flow","foam","fold","folk",
        "fond","food","fool","foot","ford","form","fort","foul","four","free",
        "fuel","full","fund","gain","game","gang","gave","gear","gene","gift",
        "girl","give","glad","glow","glue","goal","gold","gone","good","grab",
        "gray","grew","grid","grin","grip","grow","gulf","hack","half","hall",
        "halt","hand","hang","hard","harm","hate","have","head","heal","heap",
        "hear","heat","heel","held","help","here","hide","high","hill","hint",
        "hire","hold","hole","holy","home","hood","hook","hope","horn","host",
        "hour","huge","hull","hung","hunt","hurt","idea","idle","iron","item",
        "jail","join","joke","jump","just","keen","keep","kids","kill","kind",
        "king","knew","know","lack","laid","lake","land","lane","last","late",
        "lawn","lead","leaf","lean","leap","left","lend","lens","less","life",
        "lift","like","limb","line","link","list","live","load","loan","lock",
        "loft","long","look","loop","lose","loss","lost","loud","love","luck",
        "lung","made","mail","main","make","male","many","mark","mask","mass",
        "mate","math","meal","mean","meat","meet","melt","menu","mere","mesh",
        "mild","milk","mill","mind","mine","mint","miss","mode","mood","moon",
        "more","most","move","much","must","myth","nail","name","near","neck",
        "need","news","next","nice","nick","node","none","noon","norm","nose",
        "note","noun","null","once","only","open","oral","oval","oven","over",
        "page","paid","pain","pair","pale","palm","park","part","pass","past",
        "path","pave","peak","peel","peer","pick","pile","pine","pink","pipe",
        "plan","play","plot","plow","plug","plus","poem","poet","poll","pond",
        "pool","poor","pore","port","pose","post","pour","prey","prod","pull",
        "pure","push","race","rack","rage","raid","rail","rain","rank","rare",
        "rate","read","real","reap","reel","rely","rent","rest","rice","rich",
        "ride","ring","rise","risk","road","roam","roar","rock","role","roll",
        "roof","room","root","rope","rose","ruin","rule","rush","rust","safe",
        "said","sail","sale","salt","same","sand","sang","sank","save","scan",
        "seal","seam","seat","seed","seek","seem","seen","self","sell","send",
        "sent","shed","ship","shoe","shop","shot","show","shut","sick","side",
        "sign","silk","sing","sink","site","size","skin","skip","slam","slap",
        "slim","slip","slow","snap","snow","soak","sock","soft","soil","sold",
        "sole","some","song","soon","sore","sort","soul","soup","sour","span",
        "spin","spot","spur","star","stay","stem","step","stir","stop","suit",
        "sung","sunk","sure","swap","swim","tail","take","tale","tall","tank",
        "tape","task","team","tear","tell","tend","tent","term","test","than",
        "that","them","then","they","thin","this","tide","tied","till","time",
        "tiny","tire","told","toll","tone","took","tool","tops","tore","torn",
        "toss","tour","town","trap","tree","trim","trio","trip","true","tube",
        "tuck","tune","turn","twin","type","unit","upon","used","user","vain",
        "vary","vast","very","vice","view","void","vote","wade","wage","wake",
        "walk","wall","want","ward","warm","warn","wary","wash","wave","ways",
        "weak","weed","week","well","went","were","west","what","when","whom",
        "wide","wife","wild","will","wind","wine","wing","wire","wise","wish",
        "with","woke","wood","word","wore","work","worm","worn","wrap","yard",
        "year","your","zero","zone",
        # 5-letter words
        "about","above","abuse","actor","acute","admit","adopt","adult","after",
        "again","agent","agree","ahead","alarm","album","alert","alike","align",
        "alive","alley","allow","alone","along","alter","angel","anger","angle",
        "angry","anime","ankle","annex","annoy","antic","anvil","apart","apple",
        "apply","arena","argue","arise","armed","armor","aroma","arose","array",
        "aside","asset","atlas","attic","audio","audit","aunty","avail","avant",
        "avid","avoid","awake","award","aware","awful","azure","bacon","badge",
        "badly","bagel","baked","baker","basis","batch","beach","beard","began",
        "begin","being","below","bench","bible","biker","black","blade","blame",
        "bland","blank","blaze","bleak","bleed","bless","blind","blink","block",
        "blood","bloom","blown","board","bonus","boost","botch","bough","bound",
        "boxer","brace","braid","brain","brand","brave","brawl","bread","break",
        "breed","brick","bride","brief","brine","bring","brink","brook","broom",
        "brown","brush","buddy","build","built","bulge","bully","bunch","burst",
        "buyer","bylaw","cabin","cable","camel","candy","cargo","carry","catch",
        "cause","cease","chain","chair","chaos","charm","chart","chase","cheap",
        "check","cheek","cheer","chess","chest","chief","child","china","choir",
        "choke","chord","chose","chuck","chunk","churn","civil","claim","class",
        "clean","clear","clerk","click","cliff","climb","cling","clock","clone",
        "close","cloth","cloud","clown","coach","coast","cocoa","comet","comic",
        "comma","coral","could","count","court","cover","crack","craft","cramp",
        "crane","crash","crazy","cream","creek","crime","crisp","cross","crowd",
        "crown","cruel","crush","crust","crypt","cubic","curly","curry","cycle",
        "daily","dairy","dance","death","debut","delay","depot","depth","derby",
        "devil","dirty","disco","ditch","dizzy","dodge","doubt","dough","dowry",
        "draft","drain","drake","drama","drank","drape","dream","dress","dried",
        "drift","drink","drive","drove","drown","dryer","dying","eager","early",
        "earth","eight","elite","email","empty","enemy","enjoy","enter","entry",
        "equal","error","essay","event","every","exact","excel","exile","exist",
        "extra","fable","facet","faith","false","fancy","fatal","fault","feast",
        "ferry","fetch","fever","fewer","field","fiery","fifth","fifty","fight",
        "final","first","fixed","flank","flare","flash","flask","fleet","flesh",
        "float","flood","floor","flour","flown","fluid","flush","flute","focal",
        "foggy","force","forge","forum","found","frail","frame","frank","fraud",
        "fresh","front","froze","fruit","fully","funky","funny","gauge","ghost",
        "giant","given","gland","glare","glass","gleam","glide","gloom","glory",
        "gloss","glove","glyph","grace","grade","grain","grand","grant","grape",
        "grasp","grass","grate","grave","graze","greed","green","greet","grief",
        "grill","grind","groan","groin","grope","gross","group","grove","guard",
        "guess","guest","guide","guild","guile","guise","gusto","gypsy","habit",
        "happy","harsh","haste","haven","heart","heavy","hedge","hence","herbs",
        "hinge","hippo","hired","hoard","honey","honor","horse","hotel","house",
        "howdy","human","humid","humor","hurry","hyper","image","imply","inbox",
        "infer","inner","input","inter","intro","issue","ivory","japan","jewel",
        "jiffy","joint","judge","juice","juicy","kayak","knife","knock","known",
        "knack","label","large","laser","later","laugh","layer","learn","lease",
        "least","leave","legal","lemon","level","light","lilac","linen","liner",
        "liver","local","lodge","logic","loopy","lorry","lotus","lower","loyal",
        "lucky","lumpy","lunar","lyric","magic","major","maker","maple","march",
        "mayor","media","mercy","merit","metal","might","mirth","miser","model",
        "money","month","moral","motel","motor","motto","mound","mount","mourn",
        "mouth","movie","muddy","multi","music","naive","nanny","naval","nerve",
        "never","night","ninja","nitro","noble","noise","north","notch","novel",
        "nurse","nymph","occur","ocean","offer","often","olive","onset","opera",
        "optic","orbit","order","other","ought","ounce","outer","oxide","ozone",
        "panic","paper","party","pasta","patch","pause","peace","peach","pearl",
        "pedal","penny","perch","phase","phone","photo","piano","piece","pilot",
        "pitch","pixel","pizza","place","plain","plane","plant","plate","plaza",
        "pluck","plumb","plume","plunk","plush","point","poker","polar","pound",
        "power","press","price","pride","prime","print","prior","prize","probe",
        "prone","proof","prose","proud","prove","proxy","prune","psalm","pudgy",
        "pulse","punch","pupil","purse","queen","query","quest","queue","quick",
        "quiet","quota","quote","rabbi","radar","radio","raise","rally","ranch",
        "range","rapid","ratio","reach","ready","realm","rebel","refer","reign",
        "relax","remix","repay","reply","rider","rifle","right","risky","rivet",
        "robot","rouge","rough","round","route","royal","rugby","ruler","rural",
        "saint","salad","sauce","savor","scale","scare","scene","scope","score",
        "scout","scram","scrap","screw","seize","sense","serve","seven","shade",
        "shaft","shake","shall","shame","shape","share","shark","sharp","sheen",
        "sheer","shelf","shell","shift","shirt","shock","shore","short","shout",
        "shrug","siege","sight","sigma","silly","since","sixth","sixty","sized",
        "skate","skill","skull","skunk","slack","slain","slant","slash","slate",
        "slave","sleek","sleep","sleet","slept","slice","slide","slope","sloth",
        "slump","smart","smash","smell","smile","smite","smoke","smote","snake",
        "snare","sneak","sniff","solar","solid","solve","sonic","sorry","south",
        "space","spade","spare","spark","speak","spear","speed","spell","spend",
        "spice","spill","spine","spite","spoon","sport","spout","spray","spree",
        "stack","staff","stage","stain","stair","stake","stale","stall","stamp",
        "stand","stark","start","state","stave","steal","steam","steel","steep",
        "steer","stern","stick","stiff","still","sting","stink","stock","stomp",
        "stone","stood","store","storm","story","stout","stove","strap","straw",
        "strip","strut","stuck","study","stump","stung","stunk","style","sugar",
        "suite","sunny","super","surge","swamp","swear","sweat","sweep","sweet",
        "swell","swept","swift","swine","swipe","swirl","sword","swore","swung",
        "syrup","table","taunt","tense","tenth","theft","their","theme","there",
        "these","thick","thing","think","third","thorn","those","three","threw",
        "throw","thumb","thump","tidal","tiger","tight","timer","tired","title",
        "today","token","tonal","topic","total","touch","tough","towel","tower",
        "toxic","track","trade","trail","train","trait","trash","trawl","tread",
        "treat","trend","trial","tribe","tried","troop","trout","truce","truck",
        "truly","trump","trunk","truss","trust","truth","tumor","tuner","tunic",
        "tutor","tweak","twice","twirl","twist","tying","ultra","unify","union",
        "unity","until","upper","upset","urban","usage","usher","usual","utter",
        "vague","valid","value","valve","venue","viola","viral","virus","visit",
        "visor","vista","vital","vivid","vocal","voice","voter","vowel","vying",
        "wagon","waste","watch","water","weary","weave","wedge","weigh","weird",
        "whale","wheat","wheel","where","which","while","white","whole","whose",
        "wield","wince","windy","witch","woman","women","world","worry","worse",
        "worst","worth","would","wound","wrath","wrist","write","wrong","wrote",
        "yacht","yearn","yield","young","youth","zonal",
        # 6-letter words
        "access","across","acting","action","active","actual","adding","affect",
        "afford","afraid","agency","agenda","almost","always","amount","animal",
        "annual","anyone","appeal","appear","around","arrive","artist","asking",
        "aspect","attach","attack","attend","author","autumn","battle","beauty",
        "before","behind","better","bigger","blight","border","bottle","bottom",
        "bridge","bright","broken","budget","burden","button","camera","cannot",
        "castle","casual","cattle","center","change","charge","chosen","circle",
        "client","closed","closer","coffee","column","common","copper","corner",
        "county","couple","course","create","crisis","critic","custom","damage",
        "danger","debate","decide","defend","define","degree","demand","design",
        "detail","device","differ","direct","double","driven","during","effect",
        "effort","either","eleven","empire","enable","ending","energy","engage",
        "enough","ensure","entire","expert","extend","factor","fallen","family",
        "famous","figure","finger","finish","follow","forest","forget","formal",
        "former","foster","fourth","french","friend","future","garden","gather",
        "gender","global","golden","ground","growth","happen","health","hidden",
        "higher","import","indeed","inside","intent","island","itself","joined",
        "junior","kernel","launch","leader","league","letter","little","living",
        "losing","luxury","manage","manner","market","master","matter","method",
        "middle","mirror","mobile","modern","moment","mother","motion","murder",
        "museum","narrow","nation","nature","nearby","nearly","needed","normal",
        "notice","object","obtain","office","online","openly","option","orange",
        "output","parent","people","period","permit","person","phrase","planet",
        "player","please","police","policy","pretty","prince","prison","profit",
        "proper","public","pursue","rabbit","random","reason","record","refuse",
        "region","remain","remove","repair","repeat","return","reveal","review",
        "reward","rocket","roller","rubber","ruling","safety","sample","saving",
        "saying","second","secret","sector","select","senior","series","settle",
        "should","signal","silver","simple","single","sister","slight","smooth",
        "social","source","speech","spirit","spread","spring","square","statue",
        "status","steady","stolen","stream","street","stress","strong","struck",
        "studio","submit","summer","supply","surely","survey","switch","system",
        "target","taught","tennis","theory","though","threat","ticket","timber",
        "tissue","toilet","toward","travel","treaty","tunnel","typing","unable",
        "unique","unless","unlock","update","useful","valley","victim","violent",
        "virtue","vision","visual","volume","wanted","wealth","weapon","weekly",
        "weight","winner","winter","wisdom","within","wonder","wooden","writer",
    ]
    return [w for w in fallback if len(w) == length]


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
