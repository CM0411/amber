"""De kijker — een venster in haar hoofd, zonder haar op te houden.

Roadmap, fase 2 (O): "Achter de cirkel zie je haar werkelijke netwerk werken:
activaties die door de lagen stromen." En de harde regel: "Het mag haar nooit
ophouden — een uitdunning, een paar honderd waarden; de leerlus wacht nooit op
het scherm."

Daarom draait dit op de DL380 (P100 #0) terwijl zij op de X399 traint. Elke
paar seconden: pak haar nieuwste checkpoint, leg één taak voor, en vang per
geschreven teken de bedrijvigheid per laag. Dat gaat als klein JSON-bestand
naar de webpagina. De training merkt hier niets van.
"""
import sys, os, json, time, subprocess
sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinisme; determinisme.zet_vast(9001)
import checkpoint, leren, wereld, proefwerken, taken, torch

# Het wachtwoord van de rekenmachine staat búiten de repo — een repo die ooit
# openbaar wordt mag nooit een geheim in zijn geschiedenis dragen.
def _geheim():
    with open("/home/arch/.amber-geheim") as f:
        return f.read().strip()


MAP = "/home/arch/amber-werk/brein"
VERS = "/home/arch/amber-werk/fase1/nu.pt"
X399 = "arch@192.168.1.170"
HAAL_ELKE = 180          # verse momentopname van de X399, elke 3 minuten —
                         # zo vaak als ze er zelf een neerlegt

L = leren.Leerder(partij=8)
slot = proefwerken.stof()
stap_in_checkpoint = 0
laatst_gehaald = 0.0
laatst_geladen = 0.0

# Waar we haar naar laten kijken: rond haar niveau, alle families.
KEUZES = ([("rekenen", d) for d in (1, 2, 3, 4, 6, 8, 10, 12)]
          + [("code", d) for d in (1, 2, 3, 4, 5, 6, 8)]
          + [("puzzel", d) for d in (1, 2, 3, 4, 5)])

# Hooks: per doorgang de gemiddelde bedrijvigheid per laag.
huidige = []
GROEPEN = 32

def _groepen(x, n):
    per_kanaal = x.detach().abs().mean(dim=(0, 1))
    rest = per_kanaal.numel() % n
    if rest:
        per_kanaal = per_kanaal[:per_kanaal.numel() - rest]
    return [float(v) for v in per_kanaal.reshape(n, -1).mean(dim=1)]

# Het hele pad, zoals op een schema: invoer → acht lagen → uitvoer.
#   invoer  = de inbedding, in 32 groepen
#   laag    = elk blok, in 32 groepen — hoge kolommen, zoals op Cley's foto
#   uitvoer = één knoop: hoe zeker ze is van het teken dat ze kiest
def _vang_in(_m, _in, uit):
    huidige.append(("in", _groepen(uit, 32)))

def _vang_blok(_m, _in, uit):
    x = uit[0] if isinstance(uit, tuple) else uit
    huidige.append(("blok", _groepen(x, GROEPEN)))

def _vang_uit(_m, _in, uit):
    p = torch.softmax(uit.detach()[0, -1].float(), dim=-1)
    huidige.append(("uit", float(p.max())))

L.kern.inbedding.register_forward_hook(_vang_in)
for blok in L.kern.blokken:
    blok.register_forward_hook(_vang_blok)
L.kern.uitbedding.register_forward_hook(_vang_uit)


def haal_checkpoint():
    global laatst_gehaald
    laatst_gehaald = time.time()
    r = subprocess.run(
        ["sshpass", "-p", _geheim(), "scp", "-q", "-o", "ConnectTimeout=8",
         f"{X399}:~/amber-werk/fase1/leven/momentopname.pt", VERS + ".deel"],
        capture_output=True)
    if r.returncode == 0:
        os.replace(VERS + ".deel", VERS)


bedrading = None
bedrading_uit = None
wereldrand = None
geheugen_vakjes = {}
fles_stand = {}

# Haar herinneringen, uit het checkpoint — met een index om snel de meest
# gelijkende te vinden. Het zoeken is óns kijkgereedschap (gericht terugvinden
# is H, fase 4); de herinneringen zelf zijn echt: wat zij op de X399 heeft
# meegemaakt en door de flessenhals heeft onthouden.
herinneringen = []


def _grammen(tekst):
    t = tekst.replace(" ", "")
    return frozenset(t[i:i + 3] for i in range(len(t) - 2))


def _bouw_herinneringen(extra):
    global herinneringen, geheugen_vakjes, fles_stand
    herinneringen = []
    geheugen = (extra or {}).get("geheugen") or {}
    inhoud = geheugen.get("inhoud") or []
    fles = L.geheugen.flessenhals
    vakjes = {}
    tekens_totaal = 0
    for o in inhoud:
        d = fles.ontcijfer(o)
        vakjes[f"{d['familie']}/{d['graad']}"] = \
            vakjes.get(f"{d['familie']}/{d['graad']}", 0) + 1
        tekens_totaal += len(o.get("code") or ())
        if d["opgave"]:
            herinneringen.append({"opgave": d["opgave"],
                                  "oplossing": d["oplossing"],
                                  "familie": d["familie"], "graad": d["graad"],
                                  "g": _grammen(d["opgave"])})
    geheugen_vakjes = vakjes
    fles_stand = {
        "lengte": fles.lengte,
        "geweigerd": int(geheugen.get("geweigerd") or 0),
        "bezetting": round(tekens_totaal / (len(inhoud) * fles.lengte), 3)
                     if inhoud else None,
    }


def _terugdenken(taak, hoeveel=3):
    """De herinneringen die het meest op deze opgave lijken."""
    if not herinneringen:
        return []
    doel = _grammen(taak.opgave)
    if not doel:
        return []
    scores = []
    for h in herinneringen:
        overlap = len(doel & h["g"])
        if overlap:
            score = overlap / len(doel | h["g"])
            if h["familie"] == taak.familie:
                score += 0.08
            scores.append((score, h))
    scores.sort(key=lambda x: -x[0])
    uit, gezien = [], set()
    for sc, h in scores:
        if sc <= 0.12 or h["opgave"] in gezien:
            continue                     # dubbel onthouden = één gedachte
        gezien.add(h["opgave"])
        uit.append({"opgave": h["opgave"][:90], "oplossing": h["oplossing"][-24:],
                    "familie": h["familie"], "graad": h["graad"],
                    "gelijkenis": round(sc, 2)})
        if len(uit) >= hoeveel:
            break
    return uit


def _lees_bedrading():
    """Haar echte bedrading, voor het weefsel op het scherm.

    Per laag: hoe het voorwaartse blok de stroomgroepen mengt — W_omlaag ×
    W_omhoog, samengevat tot 32×32 groepen, mét teken. Groen/rood op de
    pagina is dus werkelijk plus/min in haar gewichten, zoals in het filmpje
    dat Cley aanwees. Wordt eenmalig per checkpoint berekend.
    """
    global bedrading, bedrading_uit
    n = GROEPEN
    matten = []
    with torch.no_grad():
        for blok in L.kern.blokken:
            M = blok.voorwaarts.omlaag.weight @ blok.voorwaarts.omhoog.weight
            d = M.shape[0]; g = d // n
            M = M[:g * n, :g * n].reshape(n, g, n, g).mean(dim=(1, 3))
            schaal = float(M.abs().max()) or 1.0
            matten.append([[round(float(v) / schaal, 3) for v in rij]
                           for rij in M])
        u = L.kern.uitbedding.weight.abs().mean(dim=0)
        u = u[:(u.numel() // n) * n].reshape(n, -1).mean(dim=1)
        us = float(u.max()) or 1.0
        bedrading_uit = [round(float(v) / us, 3) for v in u]
    bedrading = matten


def laad_als_nieuwer():
    global stap_in_checkpoint, laatst_geladen
    try:
        m = os.path.getmtime(VERS)
    except OSError:
        return
    if m <= laatst_geladen:
        return
    try:
        inhoud = checkpoint.lees(VERS, apparaat=L.apparaat)
        stap_in_checkpoint = checkpoint.herstel(inhoud, L.kern, L.optimizer,
                                                L.apparaat)
        global wereldrand
        extra = inhoud.get("extra") or {}
        wereldrand = extra.get("diepste_per") or None
        _bouw_herinneringen(extra)
        laatst_geladen = m
        _lees_bedrading()
    except Exception:
        pass                             # half bestand: volgende ronde weer


teller = 0
while True:
    if time.time() - laatst_gehaald > HAAL_ELKE:
        haal_checkpoint()
    laad_als_nieuwer()

    teller += 1
    trekker = taken.Trekker(9001 + teller)
    familie, diepte = KEUZES[trekker.geheel(0, len(KEUZES) - 1)]
    try:
        taak = wereld.leerreeks(familie, diepte, 1,
                                vanaf=trekker.geheel(0, 200_000),
                                uitsluiten=slot)[0]
    except Exception:
        time.sleep(2); continue

    huidige.clear()
    antwoord = L.antwoorden([taak],
                            hoogstens=leren.ruimte_voor(diepte, familie))[0]
    # `huidige` bevat nu (aantal doorgangen × 8) waarden achter elkaar
    # opknippen per doorgang: in → blokken → uit
    n_lagen = len(L.kern.blokken)
    per = 1 + n_lagen + 1
    ruw = [huidige[i:i + per] for i in range(0, len(huidige), per)]
    rijen = []
    for r in ruw:
        if len(r) == per and r[0][0] == "in" and r[-1][0] == "uit":
            rijen.append({"in": r[0][1],
                          "b": [x[1] for x in r[1:-1]],
                          "uit": round(r[-1][1], 4)})
    rijen = rijen[-48:]

    stand = {
        "tijd": time.time(),
        "herinnert": _terugdenken(taak),
        "geheugen_grootte": len(herinneringen),
        "checkpoint_stap": stap_in_checkpoint,
        "familie": familie, "diepte": diepte,
        "opgave": taak.opgave,
        "antwoord": antwoord,
        "goed": taak.nakijk(antwoord),
        "wereldrand": wereldrand,
        "geheugen_vakjes": geheugen_vakjes,
        "fles": fles_stand,
        "bedrading": bedrading,
        "bedrading_uit": bedrading_uit,
        "lagen": [{"in": [round(v, 4) for v in rij["in"]],
                   "b": [[round(v, 4) for v in laag] for laag in rij["b"]],
                   "uit": rij["uit"]} for rij in rijen],
    }
    with open(f"{MAP}/stand.json.deel", "w") as f:
        json.dump(stand, f)
    os.replace(f"{MAP}/stand.json.deel", f"{MAP}/stand.json")
    time.sleep(6)
