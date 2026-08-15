"""Bezorg de brievenbus — wat van buiten kwam gaat haar logboek in.

Draait sinds 14 aug 2026 óp de Z490: brievenbus, logboek en trainer wonen
hier allemaal, dus er komt geen ssh meer aan te pas. De brievenbus wordt
gevuld door het venster (lessen uit de vraag-tab) en door de brug (wat de
oren verstonden en het oog zag op de DL380).

Alleen draaien op een rungrens (dienst uit): het logboek op deze machine
heeft één schrijver, en dat hoort zo te blijven. Elke onbezorgde regel
uit de brievenbus wordt een `waarneming` (of een `les`) in haar logboek —
"wat van buiten kwam is bewaard" — met een doorlopend regelnummer, zodat
de hervatting hem net zo behandelt als alles wat zijzelf meemaakte.

  python3 bezorg-brievenbus.py
"""
import json
import os
import subprocess
import sys

BRIEVENBUS = "/home/arch/amber-werk/fase1/brievenbus.jsonl"
LOGBOEK = "/home/arch/amber-werk/fase1/leven/logboek.jsonl"

# 1. alleen op een rungrens
dienst = subprocess.run(["systemctl", "is-active", "amber-train"],
                        capture_output=True, text=True).stdout.strip()
if dienst == "active":
    sys.exit("de run draait — het logboek heeft één schrijver; "
             "bezorg op een rungrens")

# 2. wat ligt er te wachten? Eerst het slot: het venster (les-leer) en de
# brug (oren/oog vanaf de DL380) hangen regels aan ditzelfde bestand, en
# een aanhangsel tijdens het herschrijven van stap 5 zou stil verdwijnen.
# Het slot is een apart bestand, want de brievenbus zelf wordt omgewisseld.
import fcntl
slot = open(BRIEVENBUS + ".slot", "w")
fcntl.flock(slot, fcntl.LOCK_EX)
try:
    regels = [json.loads(r) for r in open(BRIEVENBUS)]
except FileNotFoundError:
    sys.exit("de brievenbus is leeg (bestaat nog niet)")
post = [r for r in regels if not r.get("bezorgd")]
if not post:
    sys.exit("niets onbezorgds in de brievenbus")

# 3. het regelnummer en de stap waar zij is
try:
    with open(LOGBOEK, "rb") as f:
        staart = f.readlines()[-1].decode()
except (FileNotFoundError, IndexError):
    sys.exit("kan het logboek niet lezen — niets bezorgd")
laatste = json.loads(staart)
nr = int(laatste.get("nr", 0))
stap = int(laatste.get("stap") or 0)

# 4. bezorgen, met fsync — de schrijfveiligheid komt hier uit de code
nieuwe = []
for r in post:
    nr += 1
    if r.get("soort") == "les":
        # Een les uit de vraag-tab: vraag + het júiste antwoord van Cley.
        # Wordt bij de volgende start door learn_lessons het geheugen in
        # genomen (familie "gesprek"), door de flessenhals als alles.
        nieuwe.append(json.dumps({
            "nr": nr, "tijd": r["tijd"], "soort": "les",
            "stap": stap, "bron": "cley (les)",
            "vraag": r["vraag"], "antwoord": r["antwoord"],
            "gegeven_op": r["wanneer"],
        }, ensure_ascii=False))
    elif r.get("bron") == "beeld":
        # Het oog (Qwen2.5-VL op kaart 1 van de DL380) zag een foto van
        # een rit en beschreef hem in het Nederlands. De beschrijving is
        # de waarneming; de foto zelf blijft in fase2/beelden/.
        nieuwe.append(json.dumps({
            "nr": nr, "tijd": r["tijd"], "soort": "waarneming",
            "stap": stap, "bron": "oog (beeld)",
            "tekst": r["tekst"], "gezien_op": r["wanneer"],
            "rit": r.get("rit") or "los",
        }, ensure_ascii=False))
    else:
        nieuwe.append(json.dumps({
            "nr": nr, "tijd": r["tijd"], "soort": "waarneming",
            "stap": stap, "bron": "cley (spraak)",
            "tekst": r["tekst"], "gesproken_op": r["wanneer"],
        }, ensure_ascii=False))
with open(LOGBOEK, "a") as f:
    f.write("\n".join(nieuwe) + "\n")
    f.flush()
    os.fsync(f.fileno())

# 5. afvinken (atomair herschrijven)
for r in regels:
    r["bezorgd"] = True
with open(BRIEVENBUS + ".deel", "w") as f:
    for r in regels:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
    f.flush()
    os.fsync(f.fileno())
os.replace(BRIEVENBUS + ".deel", BRIEVENBUS)
slot.close()
print(f"bezorgd: {len(post)} waarneming(en), logboek t/m regel {nr}, "
      f"bij stap {stap}")
