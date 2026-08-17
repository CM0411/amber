"""De week-1-herinneringsproef (17 aug 2026, op Cleys woord): drie bevroren
bladen uit fase1/week1-zaadjes.json — week1-onderhouden (12 lessen die in
het herhaalgeheugen blijven), week1-eenmalig (12 lessen die één keer geleerd
en nooit herhaald worden) en week1-nep (12 vragen van dezelfde vorm die
nooit geplant worden: het gokniveau). Vanaf de dag van planten draaien ze
elke 500 stappen mee; de mijlpaal over drie weken leest af hoeveel er
staat: onderhouden ≥ 80% en eenmalig boven nep.

Cley plant de 24 zelf via de vraag-tab (bij eenmalig begint de vraag met
"[eenmalig]"); dit script controleert vóór het bevriezen of elke geplante
vraag letterlijk in de brievenbus (of al bezorgd in het logboek) staat —
een tikfout maakt de meting anders stil waardeloos.

Draaien op de DL380 (moederkopie) vlak vóór de rungrens die de zaadjes
bezorgt, één keer:
  venv/bin/python fase1/week1-proefwerk.py            (controleert + bevriest)
  venv/bin/python fase1/week1-proefwerk.py --alleen-controle
"""
import json
import re
import subprocess
import sys
sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import tasks

ZAADJES = "/home/arch/amber-werk/fase1/week1-zaadjes.json"
TRAINER = "arch@192.168.1.239"

data = json.load(open(ZAADJES))
zaad = data["zaadjes"]
groepen = {"onderhouden": [], "eenmalig": [], "nep": []}
for z in zaad:
    groepen[z["groep"]].append(z)
    if not re.findall(r"-?\d+", z["antwoord"]):
        sys.exit(f"antwoord zonder getal: {z['antwoord']!r} — nakijken leest het laatste getal")
print({g: len(v) for g, v in groepen.items()})

# controle: staan de te planten vragen in de brievenbus of het logboek op de trainer?
r = subprocess.run(["ssh", "-o", "BatchMode=yes", TRAINER,
                    "cat ~/amber-werk/fase1/brievenbus.jsonl 2>/dev/null; "
                    "grep '\"soort\": \"les\"' ~/amber-werk/fase1/leven/logboek.jsonl 2>/dev/null"],
                   capture_output=True, text=True)
geplant = set()
for regel in r.stdout.splitlines():
    try:
        d = json.loads(regel)
    except Exception:
        continue
    if d.get("soort") == "les":
        v = str(d.get("vraag", "")).strip()
        if v.lower().startswith("[eenmalig]"):
            v = v[len("[eenmalig]"):].strip()
        geplant.add(v)
ontbreekt = [z["vraag"] for g in ("onderhouden", "eenmalig") for z in groepen[g]
             if z["vraag"] not in geplant]
per_ongeluk = [z["vraag"] for z in groepen["nep"] if z["vraag"] in geplant]
print(f"geplant gevonden: {sum(1 for g in ('onderhouden', 'eenmalig') for z in groepen[g] if z['vraag'] in geplant)} van 24"
      + (f"; ONTBREEKT: {ontbreekt}" if ontbreekt else "")
      + (f"; NEP TOCH GEPLANT: {per_ongeluk}" if per_ongeluk else ""))
if "--alleen-controle" in sys.argv:
    sys.exit(0)
if ontbreekt or per_ongeluk:
    sys.exit("niet bevroren: eerst de planting rechtzetten (of dit script "
             "met --forceer draaien als dat bewust is)" if "--forceer" not in sys.argv else 0)

for g, lijst in groepen.items():
    naam = f"week1-{g}"
    if exams.exists(naam):
        print(f"{naam} bestaat al — overgeslagen"); continue
    taken = [tasks.Task(family="gesprek", grade=1, number=-1,
                        problem=z["vraag"], solution=z["antwoord"]) for z in lijst]
    n = exams.freeze(naam, f"Week-1-herinneringsproef, groep {g} (17 aug 2026): "
                     + {"onderhouden": "lessen die in het herhaalgeheugen blijven",
                        "eenmalig": "lessen die één keer geleerd en nooit herhaald zijn",
                        "nep": "nooit geplant — het gokniveau"}[g]
                     + ". Antwoord = het unieke getal.", taken)
    print(f"bevroren: {naam} ({n})")
exams.forget_material()
