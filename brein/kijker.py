"""De kijker — a window into her head, without holding her up.

Roadmap, phase 2 (O): "Behind the circle you see her real network at work:
activations streaming through the layers." And the hard rule: "It must
never hold her up — a thinning, a few hundred values; the learning loop
never waits for the screen."

That is why this runs on the DL380 (P100 #0) while she trains on the
X399. Every few seconds: take her latest snapshot, put one task in front
of her, and catch per written character the activity per layer. That goes
to the web page as a small JSON file. The training notices nothing.

The stand.json keys stay Dutch: they are the interface the page reads,
and the page speaks Cley's language.
"""
import sys, os, json, time, subprocess
sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinism; determinism.lock(9001)
import bridge, exams, learning, snapshot, tasks, world, torch, tokens

# The calculator's password lives outside the repo — a repo that one day
# goes public must never carry a secret in its history.
def _secret():
    with open("/home/arch/.amber-geheim") as f:
        return f.read().strip()


FOLDER = os.environ.get("AMBER_KIJKER_MAP", "/home/arch/amber-werk/brein")
# De fijne meting (24 aug 2026): per kanaal, per kop, per feedforward-eenheid.
# Apart bestand, statisch geserveerd onder /rapport/, zodat server.py niets
# hoeft te weten en de pagina hem alleen ophaalt als er een nieuwe gedachte is.
FIJN = os.environ.get("AMBER_KIJKER_FIJN", "/home/arch/rapport/fijn.json")
EENMAAL = os.environ.get("AMBER_KIJKER_EENMAAL") == "1"     # proef: één ronde, dan stoppen
RUST = int(os.environ.get("AMBER_KIJKER_RUST", "6"))       # seconden tussen twee rondes (24 aug: 120 op de Z490, de training gaat voor)
KIJKT = os.environ.get("AMBER_KIJKER_KIJKT", "/home/arch/rapport/kijkt")   # het venster tikt dit aan bij elke stand
SLAAP_NA = int(os.environ.get("AMBER_KIJKER_SLAAP_NA", "180"))          # zo lang niemand: dan slapen (24 aug, Cleys keuze B)

def _iemand_kijkt():
    try:
        return time.time() - os.path.getmtime(KIJKT) < SLAAP_NA
    except OSError:
        return False
UREN = os.environ.get("AMBER_KIJKER_UREN", "17-23")   # 24 aug, Cley: "zet de kijker op een timer, 17:00 t/m 23:00" -- 's nachts staat het venster ook open

def _mag_kijken():
    """Binnen de uren van Cley, óf (als SLAAP_NA > 0) als hij de laatste SLAAP_NA seconden iets deed in het venster."""
    try:
        a, b = (int(x) for x in UREN.split("-"))
    except ValueError:
        a, b = 0, 24
    u = time.localtime().tm_hour
    in_uren = (a <= u < b) if a <= b else (u >= a or u < b)
    return in_uren or (SLAAP_NA > 0 and _iemand_kijkt())     # 24 aug, laat: "het moet wel echt live zijn" -- ook buiten de uren als hij er is
X399 = "arch@192.168.1.239"
FETCH_EVERY = 180        # a fresh snapshot from the X399, every 3 minutes —
                         # as often as she writes one herself

# Since 16 Aug 2026 the viewer lives on the trainer itself (the Z490, always
# on, CPU only — the card is hers): AMBER_KIJKER_LOKAAL=1 in the service.
# Then the snapshot is read in place — life.py writes it as .deel and
# renames, so a reader sees the old file or the new one, never a half —
# and nothing is fetched. Without the flag: the old road, scp from the
# trainer, for a viewer on another machine.
LOCAL = os.environ.get("AMBER_KIJKER_LOKAAL") == "1"
FRESH = ("/home/arch/amber-werk/fase1/leven/momentopname.pt" if LOCAL
         else "/home/arch/amber-werk/fase1/nu.pt")

L = learning.Learner(batch_size=8, device="cpu")   # 16 aug 2026: op de CPU — de kaarten zijn voor het leren
lock = exams.material()
step_in_snapshot = 0
last_fetched = 0.0
last_loaded = 0.0

# What we have her look at: around her level, all families.
# The choice list follows the world's own fences (world.max_depth), so a
# fence move on a rungrens arrives here by itself — the service restarts
# daily with the server. Hand-kept, this list ran three fences behind on
# 14 Aug 2026. The top fence itself is always included.
_LADDER = (1, 2, 3, 4, 5, 6, 8, 10, 13, 17, 21, 26, 32)
CHOICES = [(fam, d)
           for fam in world.FAMILIES        # 16 aug 2026: alle families van de wereld, ook "geheugen"
           for d in sorted({x for x in _LADDER if x < world.max_depth(fam)}
                           | {world.max_depth(fam)})]

# Hooks: per pass the average activity per layer.
current = []
GROUPS = 32

def _groups(x, n):
    per_channel = x.detach().abs().mean(dim=(0, 1))
    rest = per_channel.numel() % n
    if rest:
        per_channel = per_channel[:per_channel.numel() - rest]
    return [float(v) for v in per_channel.reshape(n, -1).mean(dim=1)]

# The whole path, as on a diagram: input → eight layers → output.
#   in   = the embedding, in 32 groups
#   laag = every block, in 32 groups — tall columns, as on Cley's photo
#   uit  = one node: how certain she is of the character she picks
def _catch_in(_m, _in, out):
    current.append(("in", _groups(out, 32)))

def _catch_block(_m, _in, out):
    x = out[0] if isinstance(out, tuple) else out
    # ook wat het blok zélf toevoegt (uit − in): de stroom groeit met de
    # diepte en zegt weinig over dit blok, het verschil wél — daarop rusten
    # de laagnamen (16 aug 2026); het beeld op de pagina blijft de stroom
    xin = _in[0] if isinstance(_in, tuple) else _in
    delta = x - xin if xin is not None and xin.shape == x.shape else x
    current.append(("blok", _groups(x, GROUPS), _groups(delta, GROUPS),
                    x.detach().abs().mean(dim=(0, 1))))          # fijn: per kanaal

def _catch_att(att, _in):
    # de invoer van attention.out is de uitvoer van de koppen naast elkaar:
    # per kop de gemiddelde activiteit over de posities en de kopbreedte
    x = _in[0].detach().abs()
    b, l, inner = x.shape
    per = x.reshape(b, l, att.heads, att.head_size).mean(dim=(0, 1, 3))
    current.append(("kop", [float(v) for v in per]))

def _catch_ff(_m, _in, out):
    # de invoer van feedforward.down is gelu(up(x)): de 1536 eenheden zelf
    current.append(("ff", _in[0].detach().abs().mean(dim=(0, 1))))

LIVE = os.environ.get("AMBER_KIJKER_LIVE", "/home/arch/rapport/live.json")
live_aan, live_start, live_n, live_ids, live_task, live_familie = False, 0.0, 0, [], None, ""

def _catch_out(_m, _in, out):
    global live_n
    p = torch.softmax(out.detach()[0, -1].float(), dim=-1)
    current.append(("uit", float(p.max())))
    if not live_aan:
        return
    # Live (24 aug 2026, Cley: "het moet wel echt live zijn"): na elke doorgang -- dus na elk
    # teken dat ze schrijft -- deze doorgang naar live.json, met wat ze tot nu toe schreef.
    # Het venster leest dat elke halve seconde en tekent haar denken terwijl het gebeurt.
    try:
        live_ids.append(int(p.argmax()))
        start = max(i for i, it in enumerate(current) if it[0] == "in")
        stuk = current[start:]
        rij = {"in": [round(float(v), 4) for v in stuk[0][1]],
               "b": [[round(float(v), 4) for v in it[1]] for it in stuk if it[0] == "blok"],
               "uit": round(float(p.max()), 4)}
        # per laag de 384 kanalen als cijfers 0..9 (naar het max van die laag in deze doorgang):
        # het blok van enen en nullen in het venster (24 aug laat, Cleys vierde afbeelding)
        kanaal = []
        for it in stuk:
            if it[0] == "blok" and len(it) > 3:
                v = it[3]; m = float(v.max()) or 1.0
                kanaal.append("".join(chr(48 + x) for x in (v / m * 9.999).to(torch.int64).tolist()))
        try:
            tekst = tokens.answer_from_sequence([tokens.ANSWER] + live_ids)
        except Exception:
            tekst = ""
        with open(LIVE + ".deel", "w") as f:
            json.dump({"tijd": live_start, "geschreven": time.time(), "doorgang": live_n,
                       "tekst": tekst, "opgave": getattr(live_task, "problem", ""), "familie": live_familie,
                       "checkpoint_stap": step_in_snapshot, "rij": rij, "kanaal": kanaal}, f, separators=(",", ":"))
        os.replace(LIVE + ".deel", LIVE)
        live_n += 1
    except Exception as e:
        print("live.json mislukt:", e, file=sys.stderr)

L.core.embedding.register_forward_hook(_catch_in)
L.core.unembedding.register_forward_hook(_catch_out)

# The block hooks are hung per block, and blocks come and go: adopt_shape
# (15 Aug 2026) inserts new ones when a snapshot has grown. Hooked at start
# only, the four blocks of run 6 (8 → 12, 16 Aug 2026) sent nothing, no
# pass matched `per` any more, and the window lost its waves and sparks
# while the wiring (read fresh per snapshot) was fine. So: (re)hang after
# every load, and only on blocks that do not have the hook yet.
_hooked = set()

def _hook_blocks():
    for block in L.core.blocks:
        if id(block) not in _hooked:
            block.attention.out.register_forward_hook(
                lambda m, i, o, att=block.attention: _catch_att(att, i))
            block.feedforward.down.register_forward_hook(_catch_ff)
            block.register_forward_hook(_catch_block)
            _hooked.add(id(block))

_hook_blocks()


def fetch_snapshot():
    global last_fetched
    last_fetched = time.time()
    if LOCAL:
        return                           # it is already here
    r = subprocess.run(
        ["sshpass", "-p", _secret(), "scp", "-q", "-o", "ConnectTimeout=8",
         f"{X399}:~/amber-werk/fase1/leven/momentopname.pt", FRESH + ".deel"],
        capture_output=True)
    if r.returncode == 0:
        os.replace(FRESH + ".deel", FRESH)


wiring = None
wiring_out = None
world_edge = None
memory_cells = {}
bottleneck_status = {}

# Her memories, from the snapshot — with an index to find the most alike
# quickly. The searching is our viewing tool (targeted recall is H, phase
# 4); the memories themselves are real: what she lived through on the
# X399 and kept through the bottleneck.
memories = []


def _grams(text):
    t = text.replace(" ", "")
    return frozenset(t[i:i + 3] for i in range(len(t) - 2))


def _build_memories(extra):
    global memories, memory_cells, bottleneck_status
    memories = []
    memory = (extra or {}).get("geheugen") or {}
    content = memory.get("inhoud") or []
    neck = L.memory.bottleneck
    cells = {}
    characters_total = 0
    for stored in content:
        d = neck.decode(stored)
        cells[f"{d['familie']}/{d['graad']}"] = \
            cells.get(f"{d['familie']}/{d['graad']}", 0) + 1
        characters_total += len(stored.get("code") or ())
        if d["opgave"]:
            memories.append({"opgave": d["opgave"],
                             "oplossing": d["oplossing"],
                             "familie": d["familie"], "graad": d["graad"],
                             "g": _grams(d["opgave"])})
    memory_cells = cells
    # doorzoekbaar voor het geheugen-tabblad (H-voorproef: het zoeken is
    # óns kijkgereedschap; haar eigen gerichte terugvinden is fase 4)
    try:
        with open(f"{FOLDER}/herinneringen.json.deel", "w") as f:
            json.dump([{"opgave": m["opgave"], "oplossing": m["oplossing"],
                        "familie": m["familie"], "graad": m["graad"]}
                       for m in memories], f, ensure_ascii=False)
        os.replace(f"{FOLDER}/herinneringen.json.deel",
                   f"{FOLDER}/herinneringen.json")
    except Exception:
        pass
    bottleneck_status = {
        "lengte": neck.length,
        "geweigerd": int(memory.get("geweigerd") or 0),
        "bezetting": round(characters_total / (len(content) * neck.length), 3)
                     if content else None,
    }


def _recall(task, how_many=3):
    """The memories most alike this problem."""
    if not memories:
        return []
    target = _grams(task.problem)
    if not target:
        return []
    scores = []
    for m in memories:
        overlap = len(target & m["g"])
        if overlap:
            score = overlap / len(target | m["g"])
            if m["familie"] == task.family:
                score += 0.08
            scores.append((score, m))
    scores.sort(key=lambda x: -x[0])
    out, seen = [], set()
    for sc, m in scores:
        if sc <= 0.12 or m["opgave"] in seen:
            continue                     # remembered twice = one thought
        seen.add(m["opgave"])
        out.append({"opgave": m["opgave"][:90], "oplossing": m["oplossing"][-24:],
                    "familie": m["familie"], "graad": m["graad"],
                    "gelijkenis": round(sc, 2)})
        if len(out) >= how_many:
            break
    return out


def _read_wiring():
    """Her real wiring, for the weave on the screen.

    Per layer: how the feedforward block mixes the stream groups — W_down
    × W_up, summarised to 32×32 groups, with sign. Green/red on the page
    is thus truly plus/minus in her weights, as in the clip Cley pointed
    at. Computed once per snapshot.
    """
    global wiring, wiring_out
    n = GROUPS
    mats = []
    with torch.no_grad():
        for block in L.core.blocks:
            M = block.feedforward.down.weight @ block.feedforward.up.weight
            d = M.shape[0]; g = d // n
            M = M[:g * n, :g * n].reshape(n, g, n, g).mean(dim=(1, 3))
            scale = float(M.abs().max()) or 1.0
            mats.append([[round(float(v) / scale, 3) for v in row]
                         for row in M])
        u = L.core.unembedding.weight.abs().mean(dim=0)
        u = u[:(u.numel() // n) * n].reshape(n, -1).mean(dim=1)
        us = float(u.max()) or 1.0
        wiring_out = [round(float(v) / us, 3) for v in u]
    wiring = mats


def _adopt_window(extra):
    """Follow the snapshot's window: run 4 trains at 768 while this
    Learner was built at the default. Growing changes nothing about the
    weights — proven in test-window-growth.py — so the viewer simply
    grows along, doorway included."""
    vorm = (extra or {}).get("vorm")
    if vorm:
        L.adopt_window(bridge.translate_spec(vorm).get("window") or 0)


def load_if_newer():
    global step_in_snapshot, last_loaded
    try:
        m = os.path.getmtime(FRESH)
    except OSError:
        return
    if m <= last_loaded:
        return
    try:
        content = snapshot.read(FRESH, device=L.device)
        # shape first (a grown net has more blocks; 15 Aug 2026)
        L.adopt_shape((content.get("extra") or {}).get("vorm"))
        _hook_blocks()                   # new blocks get their hook too
        step_in_snapshot = snapshot.restore(content, L.core, L.optimizer,
                                            L.device)
        global world_edge
        extra = content.get("extra") or {}
        world_edge = extra.get("diepste_per") or None
        _adopt_window(extra)
        _build_memories(extra)
        last_loaded = m
        _read_wiring()
    except Exception:
        pass                             # half a file: next round again

VRAGEN = f"{FOLDER}/vraag-wachtrij"
os.makedirs(VRAGEN, exist_ok=True)
# 25 aug 2026 (Claudes wensen, op Cleys woord in het draaiboek): twee extra
# afzenders door dezelfde weg. Een bestand "claude-*.txt" in de wachtrij is
# een vraag van Claude — het antwoord gaat naar vragen-claude.jsonl, met
# afzender, zodat in het logboek staat wie wat vroeg. Een bestand
# "dagboek-*.txt" is een vraag voor haar eigen dagboek: het antwoord komt
# ongewijzigd in sessies/dagboek-amber.md, met stap en datum. Geen
# bewerking, geen mooimakerij: wat ze zegt staat er.
VRAGEN_CLAUDE = "/home/arch/rapport/vragen-claude.jsonl"      # het venster leest /rapport/...
DAGBOEK = "/home/arch/amber/sessies/dagboek-amber.md"
DAGBOEK_JSON = "/home/arch/rapport/dagboek-amber.jsonl"


def _beantwoord_vragen():
    """Cleys vragen uit het venster: zij antwoordt met haar echte brein.

    Alles mag gevraagd worden — ook wat buiten haar wereld ligt. Dat is
    juist informatief: je ziet wat ze kan, niet wat wij ervan maken."""
    for naam in sorted(os.listdir(VRAGEN))[:3]:
        pad = os.path.join(VRAGEN, naam)
        try:
            vraag = open(pad).read().strip()[:200]
        finally:
            os.remove(pad)
        if not vraag:
            continue
        afzender = ("claude" if naam.startswith("claude-")
                    else "dagboek" if naam.startswith("dagboek-") else "cley")
        taak = tasks.Task(family="vraag", grade=1, number=0,
                          problem=vraag, solution="")
        ruim = max(16, min(500, L.core.window - len(vraag) - 16))
        antwoord = L.answer([taak], at_most=ruim)[0]
        if afzender == "cley":
            uit = {"tijd": time.time(), "vraag": vraag, "antwoord": antwoord,
                   "herinnert": _recall(taak)}
            with open(f"{FOLDER}/vraag-antwoord.json.deel", "w") as f:
                json.dump(uit, f, ensure_ascii=False)
            os.replace(f"{FOLDER}/vraag-antwoord.json.deel",
                       f"{FOLDER}/vraag-antwoord.json")
            continue
        regel = {"tijd": time.time(), "wanneer": time.strftime("%Y-%m-%d %H:%M"),
                 "stap": globals().get("step_in_snapshot"), "afzender": afzender,
                 "vraag": vraag, "antwoord": antwoord}
        doel = VRAGEN_CLAUDE if afzender == "claude" else DAGBOEK_JSON
        with open(doel, "a") as f:
            f.write(json.dumps(regel, ensure_ascii=False) + "\n")
        if afzender == "dagboek":
            os.makedirs(os.path.dirname(DAGBOEK), exist_ok=True)
            nieuw = not os.path.exists(DAGBOEK)
            with open(DAGBOEK, "a") as f:
                if nieuw:
                    f.write("# Ambers dagboek\n\nHaar eigen woorden, ongewijzigd. Elke regel: wanneer, "
                            "bij welke stap van haar brein, de vraag, en wat zij zei.\n\n")
                f.write(f"- **{regel['wanneer']}** · stap **{regel['stap']}** · "
                        f"*{vraag}* — {antwoord}\n")


# --- laagnamen uit haar meting (16 aug 2026, Cleys keuze) ---------------------
# Elke laag krijgt in het venster de naam van de familie die hem het meest
# laat oplichten. Per familie een lopend gemiddelde van de activiteit per
# laag (over de doorgangen en de 32 groepen van elke opgave die de kijker
# haar voorlegt); per laag wordt dat gemiddelde gedeeld door het eigen
# gemiddelde van die familie over alle lagen — zo telt niet wie het hardst
# roept maar wie deze laag naar verhouding het meest gebruikt. De hoogste
# wint; ligt de tweede binnen vijf procent, dan heet de laag "gemengd".
# Gemeten op wat elk blok zélf toevoegt (uit − in), niet op de stroom.
# Namen zijn dus een meting en veranderen mee met haar — de teller reist
# mee in een eigen standbestand, zodat een herstart niet bij nul begint.
LAAGNAMEN = {"rekenen": "rekenlaag", "code": "codelaag",
             "puzzel": "puzzellaag", "geheugen": "geheugenlaag",
             "logica": "logicalaag", "volgorde": "volgordelaag",
             "tekst": "tekstlaag", "zeggen": "zeggenlaag", "taal": "taallaag",
             "machine": "machinelaag", "tellen": "tellenlaag", "antwoord": "antwoordlaag"}
LAAGSTAND = f"{FOLDER}/laagnamen-stand.json"
MINSTENS = 20                            # opgaven per familie vóór hij meetelt
try:
    laagtel = json.load(open(LAAGSTAND))
except Exception:
    laagtel = {}                         # familie -> {"n": aantal, "som": [per laag]}


def _tel_lagen(family, rows):
    """Neem de activiteit per laag van deze opgave op in het lopend gemiddelde."""
    if not rows:
        return
    n_layers = len(rows[0]["d"])
    per_laag = [sum(sum(row["d"][l]) / max(1, len(row["d"][l])) for row in rows) / len(rows)
                for l in range(n_layers)]
    t = laagtel.setdefault(family, {"n": 0, "som": [0.0] * n_layers})
    if len(t["som"]) != n_layers:        # gegroeid: opnieuw beginnen voor deze familie
        t["n"], t["som"] = 0, [0.0] * n_layers
    t["n"] += 1
    t["som"] = [a + b for a, b in zip(t["som"], per_laag)]
    try:
        with open(LAAGSTAND + ".deel", "w") as f:
            json.dump(laagtel, f)
        os.replace(LAAGSTAND + ".deel", LAAGSTAND)
    except Exception:
        pass


def _laagnamen():
    """Per laag: welke familie hem naar verhouding het meest gebruikt."""
    profiel = {}
    for fam, t in laagtel.items():
        if t["n"] < MINSTENS or not t["som"]:
            continue
        gem = [x / t["n"] for x in t["som"]]
        eigen = sum(gem) / len(gem) or 1.0
        profiel[fam] = [g / eigen for g in gem]
    if len(profiel) < 2:
        return []
    n_layers = min(len(v) for v in profiel.values())
    # hoe hard werkt elke laag überhaupt (over alle families samen)? Een
    # laag die nog nauwelijks iets toevoegt — de verse blokken na een
    # groei, poorten nog bijna dicht — heet "stil": daar zou een familie-
    # naam alleen ruis benoemen (gezien 16 aug 2026 bij lagen 9–12)
    hardte = []
    for l in range(n_layers):
        hardte.append(sum(t["som"][l] / t["n"] for fam, t in laagtel.items()
                          if fam in profiel) / len(profiel))
    # tegen de middelste laag afgezet, niet tegen de hardste: het laatste
    # oude blok werkt tien keer harder dan de eerste en zou anders ook
    # een echte, getrainde laag 1 "stil" laten heten
    midden = sorted(hardte)[len(hardte) // 2] or 1.0
    uit = []
    for l in range(n_layers):
        if hardte[l] < 0.05 * midden:
            uit.append({"laag": l + 1, "familie": None, "naam": "stil",
                        "sterkte": None})
            continue
        kandidaten = sorted(((v[l], fam) for fam, v in profiel.items()), reverse=True)
        (s1, f1), (s2, _) = kandidaten[0], kandidaten[1]
        gemengd = s1 < 1.05 * s2
        uit.append({"laag": l + 1,
                    "familie": None if gemengd else f1,
                    "naam": "gemengd" if gemengd else LAAGNAMEN.get(f1, f1 + "laag"),
                    "sterkte": round(s1 / s2, 3) if s2 else None})
    return uit


counter = 0
def _kwant(vecs, per_blok_max=None):
    """Lijst van tensors -> lijst van lijsten met gehele getallen 0..255,
    ten opzichte van het maximum (per blok, over alle doorgangen)."""
    uit = []
    for i, v in enumerate(vecs):
        m = per_blok_max[i] if per_blok_max is not None else float(v.max())
        m = m or 1.0
        uit.append([int(round(255 * float(x) / m)) for x in v])
    return uit

def _schrijf_fijn(tijd, rows, n_layers):
    """De fijne meting van deze gedachte: per doorgang per blok de 384 kanalen,
    de koppen en de feedforward in 48 groepen; per blok het gemiddelde van
    de 1536 feedforward-eenheden over de hele gedachte. Alles 0..255 ten
    opzichte van het maximum van dat blok in deze gedachte, zodat de pagina
    alleen verhoudingen hoeft te tonen en het bestand klein blijft."""
    if not rows:
        return
    ff_n = int(rows[0]["ff"][0].numel()) if rows[0]["ff"] else 0
    kan_max = [max(float(r["fijn"][k].max()) for r in rows) or 1.0 for k in range(n_layers)]
    ff_max = [max(float(r["ff"][k].max()) for r in rows) or 1.0 for k in range(n_layers)] if ff_n else []
    kop_max = [max(max(r["kop"][k]) for r in rows) or 1.0 for k in range(n_layers)] if rows[0]["kop"] else []
    ff_som = [sum(r["ff"][k] for r in rows) / len(rows) for k in range(n_layers)] if ff_n else []
    fijn = {
        "tijd": tijd, "checkpoint_stap": step_in_snapshot, "lagen": n_layers,
        "koppen": len(rows[0]["kop"][0]) if rows[0]["kop"] else 0, "eenheden": ff_n, "kanalen": int(rows[0]["fijn"][0].numel()),
        "doorgangen": len(rows),
        "kanaal": [_kwant(r["fijn"], kan_max) for r in rows],
        "kop": [[[int(round(255 * v / kop_max[k])) for v in r["kop"][k]] for k in range(n_layers)] for r in rows] if kop_max else [],
        "ff_groep": [_kwant([_groups_t(r["ff"][k], 48) for k in range(n_layers)], ff_max) for r in rows] if ff_n else [],
        "ff_eenheid": _kwant(ff_som) if ff_n else [],
    }
    with open(FIJN + ".deel", "w") as f:
        json.dump(fijn, f, separators=(",", ":"))
    os.replace(FIJN + ".deel", FIJN)

def _groups_t(v, n):
    rest = v.numel() % n
    if rest:
        v = v[:v.numel() - rest]
    return v.reshape(n, -1).mean(dim=1)

while True:
    if time.time() - last_fetched > FETCH_EVERY:
        fetch_snapshot()
    _beantwoord_vragen()
    load_if_newer()
    # Slapen buiten Cleys uren (24 aug 2026): de kijker kostte de training 13%, en 's nachts
    # staat het venster toch open. Binnen de uren: elke RUST seconden een ronde (en met
    # SLAAP_NA > 0 alleen als het venster KIJKT aantikt). Cleys vragen worden ook slapend
    # beantwoord (hierboven); een proefstand (EENMAAL) slaapt nooit.
    if not EENMAAL and not _mag_kijken():
        time.sleep(30)
        continue

    counter += 1
    picker = tasks.Picker(9001 + counter)
    family, depth = CHOICES[picker.integer(0, len(CHOICES) - 1)]
    try:
        task = world.learning_tasks(family, depth, 1,
                                    start=picker.integer(0, 200_000),
                                    room=L.core.window - 112,
                                    exclude=lock)[0]
    except Exception:
        time.sleep(2); continue

    current.clear()
    live_start, live_n, live_task, live_familie = time.time(), 0, task, family
    live_ids.clear(); live_aan = True
    answer = L.answer([task],
                      at_most=learning.room_for(depth, family,
                                                L.core.window))[0]
    live_aan = False
    # `current` now holds (passes × 8) values in a row
    # cut per pass: in → blocks → out
    n_layers = len(L.core.blocks)
    # per doorgang: in, dan per blok kop/ff/blok, dan uit -- gesneden op merkje
    rows, rij = [], None
    for item in current:
        tag = item[0]
        if tag == "in":
            rij = {"in": item[1], "b": [], "d": [], "fijn": [], "kop": [], "ff": []}
        elif rij is None:
            continue
        elif tag == "kop":
            rij["kop"].append(item[1])
        elif tag == "ff":
            rij["ff"].append(item[1])
        elif tag == "blok":
            rij["b"].append(item[1]); rij["d"].append(item[2]); rij["fijn"].append(item[3])
        elif tag == "uit":
            rij["uit"] = round(item[1], 4)
            if len(rij["b"]) == n_layers:
                rows.append(rij)
            rij = None
    rows = rows[-48:]
    _tel_lagen(family, rows)

    stand = {
        "tijd": live_start,             # de begintijd van deze gedachte: gelijk aan live.json (24 aug)
        "laagnamen": _laagnamen(),
        "herinnert": _recall(task),
        "geheugen_grootte": len(memories),
        "checkpoint_stap": step_in_snapshot,
        "familie": family, "diepte": depth,
        "opgave": task.problem,
        "antwoord": answer,
        "goed": task.check(answer),
        "wereldrand": world_edge,
        "geheugen_vakjes": memory_cells,
        "fles": bottleneck_status,
        "bedrading": wiring,
        "bedrading_uit": wiring_out,
        "lagen": [{"in": [round(v, 4) for v in row["in"]],
                   "b": [[round(v, 4) for v in layer] for layer in row["b"]],
                   "uit": row["uit"]} for row in rows],
    }
    with open(f"{FOLDER}/stand.json.deel", "w") as f:
        json.dump(stand, f)
    os.replace(f"{FOLDER}/stand.json.deel", f"{FOLDER}/stand.json")
    try:
        _schrijf_fijn(stand["tijd"], rows, n_layers)
    except Exception as e:
        print("fijn.json mislukt:", e, file=sys.stderr)
    if EENMAAL:
        break
    time.sleep(RUST)
