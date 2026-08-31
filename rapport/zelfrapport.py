"""Het zelfrapport — de eerste trede van zelfverbetering (18 aug 2026, Cley).

Elk kwartier (met amber-rapport.service) leest dit script haar eigen
proefwerken, keuzes en wereldstand en schrijft een kort VOORSTEL: welk vak
stokt, waar zij vergeet, welk hek open kan, waar haar keuzes scheef
zitten. Alleen voorstellen, nooit uitvoeren — Cley beslist, en zwijgen is
nee. Twee stemmen, duidelijk gelabeld:

  * het systeem: regels over de meetgegevens (dit bestand);
  * Amber zelf ("Amber zegt: …"): zodra de familie "zeggen" in haar wereld
    zit, krijgt zij de echte stand in precies het formaat van die familie
    voorgelegd en schrijft zij haar eigen zin — op de CPU, uit de laatste
    momentopname, buiten de trainer om. Ervoor staat er dat zij het nog
    niet geleerd heeft.

Uitvoer: /home/arch/rapport/zelfrapport.json (het venster leest het onder
/rapport/zelfrapport.json). Melding aan Cley via ntfy: hooguit één per
dag, en bij een nieuwe run (rungrens) meteen — nooit per proefwerk.
Groeit later door naar G (eigen oefenmateriaal): de voorstellen zijn de
kiem, het uitvoeren blijft aan de roadmap en aan Cleys akkoord.

  python3 zelfrapport.py            # schrijven (en melden als het mag)
  python3 zelfrapport.py --droog    # alleen printen, niets schrijven
"""
import json
import os
import re
import sys
import time
import urllib.request

RAPPORT = "/home/arch/rapport"
UIT = f"{RAPPORT}/zelfrapport.json"
TIJDLIJN = f"{RAPPORT}/tijdlijn.json"
RUNJSON = f"{RAPPORT}/run.json"
LOGBOEK = "/home/arch/amber-werk/fase1/leven/logboek.jsonl"
OPNAME = "/home/arch/amber-werk/fase1/leven/momentopname.pt"
KERN = "/home/arch/amber-werk/kern"
KANAALBESTAND = "/home/arch/.amber-ntfy"
DROOG = "--droog" in sys.argv

# Bladen die één familie meten (voor "stokt" en "vergeet" per vak); de
# rest (grondslag, gemengd, ladder, …) telt als geheel.
FAMILIE_VAN_BLAD = {"regel": "puzzel", "regelcheck": "puzzel", "rooster": "puzzel",
                    "diepte": "puzzel", "geheugen": "geheugen", "geheugen2": "geheugen",
                    "logica": "logica", "volgorde": "volgorde", "tekst": "tekst",
                    "vergelijking": "rekenen", "deling": "rekenen", "zeggen": "zeggen",
                    "taal": "taal", "gesprek": "rekenen", "machine": "machine", "tellen": "tellen", "antwoord": "antwoord"}
STOKT_ONDER = 60          # score waaronder een blad "stokt" …
STOKT_STAPPEN = 3000      # … als het over zoveel stappen niet meer dan
STOKT_MARGE = 3           # zoveel punten vooruitging
VERGEET_DALING = 10       # punten onder de eigen top = vergeten
KEUZE_VENSTER = 500       # stappen waarover de keuzes tellen


def lees(pad, anders):
    try:
        with open(pad) as f:
            return json.load(f)
    except Exception:
        return anders


def hekken(tekst):
    return {f: int(d) for f, d in re.findall(r"(\w+) (\d+)", tekst or "")}


tijdlijn = lees(TIJDLIJN, {})
run = lees(RUNJSON, {})
punten = {int(k): v for k, v in (tijdlijn.get("punten") or {}).items()}
if not punten:
    sys.exit("geen proefwerkpunten — niets te zeggen")
stappen = sorted(punten)
laatste = stappen[-1]
scores = punten[laatste]
hek = hekken(run.get("hek"))
start = int(run.get("start") or 0)
rand = {}
for fam, per in (tijdlijn.get("wereld") or {}).items():
    if per:
        rand[fam] = per[max(per, key=int)]
for fam in hek:
    rand.setdefault(fam, 2)

# --- keuzes over de laatste KEUZE_VENSTER stappen ------------------------------
keuzes = {}
try:
    with open(LOGBOEK) as f:
        regels = f.readlines()[-20000:]
    for regel in regels:
        try:
            r = json.loads(regel)
        except Exception:
            continue
        if r.get("soort") == "stap" and r.get("familie") and r.get("stap", 0) > laatste - KEUZE_VENSTER:
            keuzes[r["familie"]] = keuzes.get(r["familie"], 0) + 1
except OSError:
    pass
n_keuzes = sum(keuzes.values()) or 1
aandeel = {f: round(100 * n / n_keuzes) for f, n in keuzes.items()}

# --- de regels van het systeem --------------------------------------------------
voorstellen = []
waarnemingen = []


def blad_bij(stap):
    return punten.get(stap, {})


for blad, score in sorted(scores.items()):
    if blad.startswith("week1"):
        continue
    reeks = [(s, punten[s][blad]) for s in stappen if blad in punten[s] and s >= start]
    top = max((v for _, v in reeks), default=score)
    fam = FAMILIE_VAN_BLAD.get(blad)
    # stokt: laag en al STOKT_STAPPEN stappen niet vooruit
    eerder = [v for s, v in reeks if s <= laatste - STOKT_STAPPEN]
    if score < STOKT_ONDER and eerder and score - eerder[-1] <= STOKT_MARGE and laatste - start >= STOKT_STAPPEN:
        waarnemingen.append(f"{blad} stokt: {score}% en in {STOKT_STAPPEN} stappen niet vooruit")
        if fam:
            voorstellen.append(f"{fam}: kleinere stap tussen de dieptes of een brug-steen vóór {blad}")
    # vergeet: onder de eigen top van deze run
    if top - score >= VERGEET_DALING and score < 90:
        waarnemingen.append(f"{blad} zakt: {score}% tegen top {top}% in deze run")
        if fam:
            voorstellen.append(f"{fam}: meer herhaling of het hek even laten staan")

# hekken die open kunnen: rand op het hek en de familie kan het
for fam, grens in hek.items():
    if rand.get(fam, 0) >= grens:
        bladen = [b for b, f in FAMILIE_VAN_BLAD.items() if f == fam and b in scores]
        goed = all(scores[b] >= 85 for b in bladen) if bladen else True
        if goed:
            voorstellen.append(f"{fam}: hek {grens} is bereikt en de bladen staan hoog — hek kan omhoog bij de knip")
        else:
            waarnemingen.append(f"{fam}: hek {grens} bereikt maar de bladen niet hoog ({', '.join(f'{b} {scores[b]}%' for b in bladen)})")

# keuzes: een familie die zij mijdt terwijl die laag staat, of overvraagt
if keuzes:
    fams = sorted(set(hek) | set(keuzes))
    eerlijk = 100 // max(1, len(fams))
    for fam in fams:
        deel = aandeel.get(fam, 0)
        bladen = [b for b, f in FAMILIE_VAN_BLAD.items() if f == fam and b in scores]
        laag = bladen and min(scores[b] for b in bladen) < STOKT_ONDER
        if laag and deel < eerlijk // 2:
            waarnemingen.append(f"{fam}: laag maar maar {deel}% van haar keuzes")
            voorstellen.append(f"{fam}: nieuwsgierigheid trekt er te weinig — bodem verhogen of les geven")
        if deel >= 2 * eerlijk and not laag:
            waarnemingen.append(f"{fam}: {deel}% van haar keuzes terwijl het al goed gaat")

# --- Amber zelf: haar eigen zin, als "zeggen" in haar wereld zit ----------------
amber_zegt = None
amber_noot = None
amber_vraagt = None
try:
    sys.path.insert(0, KERN)
    import world as _world                     # de wereld van de lopende run
    if "zeggen" in _world.FAMILIES:
        # de echte stand in het formaat van de familie: per familie het laagste
        # familieblad (of grondslag voor de gemeten drie), rand/hek, keuzes
        fams = [f for f in _world.ZEG_ONDERWERPEN if f in hek]
        cijfers = {}
        for fam in fams:
            bladen = [b for b, f in FAMILIE_VAN_BLAD.items() if f == fam and b in scores]
            if bladen:
                cijfers[fam] = min(scores[b] for b in bladen)
            elif fam in ("rekenen", "code", "puzzel") and "grondslag" in scores:
                cijfers[fam] = scores["grondslag"]
        # vier families met verschillende cijfers, zoals de familie het kent
        gekozen = []
        for fam in sorted(cijfers, key=cijfers.get):
            if cijfers[fam] not in [cijfers[g] for g in gekozen]:
                gekozen.append(fam)
            if len(gekozen) == 4:
                break
        if len(gekozen) >= 2:
            regels_ = ["cijfers: " + " ; ".join(f"{f} {cijfers[f]}" for f in gekozen),
                       "wereld: " + " ; ".join(f"{f} {rand.get(f, 2)}/{hek.get(f, 12)}" for f in gekozen),
                       "keuzes: " + " ; ".join(f"{f} {aandeel.get(f, 0)}" for f in gekozen),
                       "wat wil je?"]
            vraag = "\n".join(regels_)
            os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
            import determinism; determinism.lock(1)
            import torch
            import learning, snapshot, bridge, tasks as _tasks
            L = learning.Learner(batch_size=1)
            inhoud = snapshot.read(OPNAME, device="cpu")
            extra = inhoud.get("extra") or {}
            if extra.get("vorm"):
                L.adopt_shape(bridge.translate_spec(extra["vorm"]))
            snapshot.restore(inhoud, L.core, None, "cpu")
            taak = _tasks.Task(family="zeggen", grade=9, number=0, problem=vraag, solution="", working=None)
            with torch.no_grad():
                antwoord = L.answer([taak], at_most=learning.room_for(9, "zeggen", L.core.window))[0]
            amber_zegt = antwoord.rsplit(" ; ", 1)[-1].strip()
            amber_noot = "haar eigen zin, uit de laatste momentopname; de vraag: " + vraag.replace("\n", " / ")
            # Gesprek (19 aug 2026, Cley): staat 'zeggen' tot >= 19 open, dan
            # vragen we haar ook echt iets te VRAGEN — dat is de zin die
            # Cley kan beantwoorden (graad 19-20: "mag ik ... ?").
            amber_vraagt = None
            if rand.get("zeggen", 0) >= 19:
                vraag2 = "\n".join(regels_[:2] + ["wat vraag je aan cley?"])
                taak2 = _tasks.Task(family="zeggen", grade=19, number=0, problem=vraag2, solution="", working=None)
                with torch.no_grad():
                    a2 = L.answer([taak2], at_most=learning.room_for(19, "zeggen", L.core.window))[0]
                amber_vraagt = a2.rsplit(" ; ", 1)[-1].strip()
            # Logboek van haar uitspraken (aangroeiend; overleeft runs)
            try:
                import json as _json, time as _time
                rec = {"tijd": _time.time(), "wanneer": _time.strftime("%Y-%m-%d %H:%M"),
                       "run": run.get("naam"), "stap": laatste,
                       "zegt": amber_zegt, "vraagt": amber_vraagt,
                       "vraag_aan_haar": vraag.replace("\n", " / "),
                       "cijfers": cijfers, "antwoord_cley": None}
                with open(f"{RAPPORT}/amber-zegt.jsonl", "a") as _f:
                    _f.write(_json.dumps(rec, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # I-steen (31 aug 2026, Cleys woord): een níéuwe vraag van haar
            # gaat meteen naar Cleys telefoon — een vraag die niemand hoort
            # is geen vraag. Alleen bij verandering, en hooguit één melding
            # per 90 minuten, zodat wisselen tussen twee vragen niet spamt.
            try:
                MELD = f"{RAPPORT}/vraag-gemeld.json"
                st_ = lees(MELD, {})
                if (amber_vraagt and not DROOG
                        and amber_vraagt != st_.get("vraag")
                        and time.time() - float(st_.get("tijd") or 0) >= 90 * 60):
                    kanaal_ = open(KANAALBESTAND).read().strip()
                    tekst_ = (f"{amber_vraagt}\n"
                              "antwoorden kan in het venster (open vragen); "
                              "zwijgen is wachten")
                    req_ = urllib.request.Request(
                        f"https://ntfy.sh/{kanaal_}", data=tekst_.encode(),
                        headers={"Title": "Amber vraagt",
                                 "Tags": "speech_balloon"})
                    urllib.request.urlopen(req_, timeout=15)
                    with open(MELD + ".deel", "w") as _f:
                        json.dump({"vraag": amber_vraagt, "tijd": time.time(),
                                   "stap": laatste}, _f, ensure_ascii=False)
                    os.replace(MELD + ".deel", MELD)
            except Exception as _e:
                print("vraag-melding mislukte:", _e)
    else:
        amber_noot = "de familie 'zeggen' zit nog niet in haar wereld — vanaf de volgende knip vertelt zij het zelf"
except Exception as e:
    amber_noot = f"kon haar niet vragen: {e}"

uit = {
    "gemaakt": time.strftime("%Y-%m-%d %H:%M"),
    "run": run.get("naam"), "stap": laatste,
    "waarnemingen": waarnemingen,
    "voorstellen": voorstellen or ["niets bijzonders — zo doorgaan"],
    "amber_zegt": amber_zegt, "amber_noot": amber_noot,
    "amber_vraagt": (amber_vraagt if "amber_vraagt" in dir() else None),
    "keuzes": aandeel,
    "regel": "alleen voorstellen — Cley beslist, zwijgen is nee",
}
if DROOG:
    print(json.dumps(uit, ensure_ascii=False, indent=1))
    sys.exit(0)

vorig = lees(UIT, {})
with open(UIT + ".deel", "w") as f:
    json.dump(uit, f, ensure_ascii=False)
os.replace(UIT + ".deel", UIT)

# --- melden: hooguit één per dag, of meteen bij een nieuwe run --------------------
nu = time.time()
gemeld_op = float(vorig.get("gemeld_op") or 0)
nieuwe_run = vorig.get("run") != run.get("naam")
if (nu - gemeld_op >= 24 * 3600 or nieuwe_run) and (voorstellen or amber_zegt) and vorig.get("stap") != laatste:
    try:
        kanaal = open(KANAALBESTAND).read().strip()
        tekst = f"stap {laatste:,} · " + " · ".join(voorstellen[:3])
        if amber_zegt:
            tekst += f"\nAmber zegt: {amber_zegt}"
        tekst += "\n(alleen voorstellen — jij beslist)"
        req = urllib.request.Request(f"https://ntfy.sh/{kanaal}", data=tekst.encode(),
                                     headers={"Title": "Amber stelt voor", "Priority": "low", "Tags": "brain"})
        urllib.request.urlopen(req, timeout=15)
        uit["gemeld_op"] = nu
        with open(UIT + ".deel", "w") as f:
            json.dump(uit, f, ensure_ascii=False)
        os.replace(UIT + ".deel", UIT)
    except Exception as e:
        print("melden mislukte:", e)
else:
    uit["gemeld_op"] = gemeld_op
    with open(UIT + ".deel", "w") as f:
        json.dump(uit, f, ensure_ascii=False)
    os.replace(UIT + ".deel", UIT)
print(f"zelfrapport: {len(waarnemingen)} waarnemingen, {len(voorstellen)} voorstellen"
      + (f", Amber zegt: {amber_zegt}" if amber_zegt else ""))
