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
import bridge, exams, learning, snapshot, tasks, world, torch

# The calculator's password lives outside the repo — a repo that one day
# goes public must never carry a secret in its history.
def _secret():
    with open("/home/arch/.amber-geheim") as f:
        return f.read().strip()


FOLDER = "/home/arch/amber-werk/brein"
FRESH = "/home/arch/amber-werk/fase1/nu.pt"
X399 = "arch@192.168.1.239"
FETCH_EVERY = 180        # a fresh snapshot from the X399, every 3 minutes —
                         # as often as she writes one herself

L = learning.Learner(batch_size=8)
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
           for fam in ("rekenen", "code", "puzzel")
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
    current.append(("blok", _groups(x, GROUPS)))

def _catch_out(_m, _in, out):
    p = torch.softmax(out.detach()[0, -1].float(), dim=-1)
    current.append(("uit", float(p.max())))

L.core.embedding.register_forward_hook(_catch_in)
for block in L.core.blocks:
    block.register_forward_hook(_catch_block)
L.core.unembedding.register_forward_hook(_catch_out)


def fetch_snapshot():
    global last_fetched
    last_fetched = time.time()
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
        taak = tasks.Task(family="vraag", grade=1, number=0,
                          problem=vraag, solution="")
        ruim = max(16, min(500, L.core.window - len(vraag) - 16))
        antwoord = L.answer([taak], at_most=ruim)[0]
        uit = {"tijd": time.time(), "vraag": vraag, "antwoord": antwoord,
               "herinnert": _recall(taak)}
        with open(f"{FOLDER}/vraag-antwoord.json.deel", "w") as f:
            json.dump(uit, f, ensure_ascii=False)
        os.replace(f"{FOLDER}/vraag-antwoord.json.deel",
                   f"{FOLDER}/vraag-antwoord.json")


counter = 0
while True:
    if time.time() - last_fetched > FETCH_EVERY:
        fetch_snapshot()
    _beantwoord_vragen()
    load_if_newer()

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
    answer = L.answer([task],
                      at_most=learning.room_for(depth, family,
                                                L.core.window))[0]
    # `current` now holds (passes × 8) values in a row
    # cut per pass: in → blocks → out
    n_layers = len(L.core.blocks)
    per = 1 + n_layers + 1
    raw = [current[i:i + per] for i in range(0, len(current), per)]
    rows = []
    for r in raw:
        if len(r) == per and r[0][0] == "in" and r[-1][0] == "uit":
            rows.append({"in": r[0][1],
                         "b": [x[1] for x in r[1:-1]],
                         "uit": round(r[-1][1], 4)})
    rows = rows[-48:]

    stand = {
        "tijd": time.time(),
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
    time.sleep(6)
