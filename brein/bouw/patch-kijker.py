"""Maakt de kijker fijner (24 aug 2026): per kanaal, per aandachtskop en per
feedforward-eenheid, naar rapport/fijn.json — naast stand.json, dat blijft
zoals het was. Met een proefstand: AMBER_KIJKER_MAP=<map> AMBER_KIJKER_FIJN=<pad>
AMBER_KIJKER_EENMAAL=1 draait één ronde in een eigen map en stopt.
Gebruik:  python3 patch-kijker.py /pad/naar/kijker.py
"""
import sys, ast, shutil, time
pad = sys.argv[1]
s = open(pad).read()

def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)

# 1. paden en de proefstand
rep('FOLDER = "/home/arch/amber-werk/brein"\n',
'''FOLDER = os.environ.get("AMBER_KIJKER_MAP", "/home/arch/amber-werk/brein")
# De fijne meting (24 aug 2026): per kanaal, per kop, per feedforward-eenheid.
# Apart bestand, statisch geserveerd onder /rapport/, zodat server.py niets
# hoeft te weten en de pagina hem alleen ophaalt als er een nieuwe gedachte is.
FIJN = os.environ.get("AMBER_KIJKER_FIJN", "/home/arch/rapport/fijn.json")
EENMAAL = os.environ.get("AMBER_KIJKER_EENMAAL") == "1"     # proef: één ronde, dan stoppen
''')

# 2. de hooks: het blok ook per kanaal, en de koppen en de feedforward erbij
rep('''    current.append(("blok", _groups(x, GROUPS), _groups(delta, GROUPS)))
''',
'''    current.append(("blok", _groups(x, GROUPS), _groups(delta, GROUPS),
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
''')
rep('''    for block in L.core.blocks:
        if id(block) not in _hooked:
            block.register_forward_hook(_catch_block)
            _hooked.add(id(block))''',
'''    for block in L.core.blocks:
        if id(block) not in _hooked:
            block.attention.out.register_forward_hook(
                lambda m, i, o, att=block.attention: _catch_att(att, i))
            block.feedforward.down.register_forward_hook(_catch_ff)
            block.register_forward_hook(_catch_block)
            _hooked.add(id(block))''')

# 3. rijen per doorgang op merkje, niet meer op vaste lengte
rep('''    n_layers = len(L.core.blocks)
    per = 1 + n_layers + 1
    raw = [current[i:i + per] for i in range(0, len(current), per)]
    rows = []
    for r in raw:
        if len(r) == per and r[0][0] == "in" and r[-1][0] == "uit":
            rows.append({"in": r[0][1],
                         "b": [x[1] for x in r[1:-1]],
                         "d": [x[2] for x in r[1:-1]],   # de eigen bijdrage per blok
                         "uit": round(r[-1][1], 4)})
    rows = rows[-48:]''',
'''    n_layers = len(L.core.blocks)
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
    rows = rows[-48:]''')

# 4. fijn.json schrijven, gekwantiseerd naar 0..255 per blok
rep('''    with open(f"{FOLDER}/stand.json.deel", "w") as f:
        json.dump(stand, f)
    os.replace(f"{FOLDER}/stand.json.deel", f"{FOLDER}/stand.json")
    time.sleep(6)''',
'''    with open(f"{FOLDER}/stand.json.deel", "w") as f:
        json.dump(stand, f)
    os.replace(f"{FOLDER}/stand.json.deel", f"{FOLDER}/stand.json")
    try:
        _schrijf_fijn(stand["tijd"], rows, n_layers)
    except Exception as e:
        print("fijn.json mislukt:", e, file=sys.stderr)
    if EENMAAL:
        break
    time.sleep(6)''')

rep('''while True:
    if time.time() - last_fetched > FETCH_EVERY:''',
'''def _kwant(vecs, per_blok_max=None):
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
    if time.time() - last_fetched > FETCH_EVERY:''')

ast.parse(s)
shutil.copy2(pad, pad + ".voor-fijn-" + time.strftime("%Y%m%d-%H%M"))
open(pad, "w").write(s)
print("kijker.py: fijne meting erbij (per kanaal, per kop, per feedforward-eenheid); leest goed")
