"""Bezorg de brievenbus — Cleys verstane spraakmemo's haar logboek in.

Alleen draaien op een rungrens (dienst uit): het logboek op de trainer
heeft één schrijver, en dat hoort zo te blijven. Elke onbezorgde regel
uit de brievenbus wordt een `waarneming` in haar logboek — "wat van
buiten kwam is bewaard" — met een doorlopend regelnummer, zodat de
hervatting hem net zo behandelt als alles wat zijzelf meemaakte.

  venv/bin/python fase1/bezorg-brievenbus.py
"""
import json
import os
import subprocess
import sys
import time

BRIEVENBUS = "/home/arch/amber-werk/fase1/brievenbus.jsonl"
TRAINER = "arch@192.168.1.239"
LOGBOEK = "~/amber-werk/fase1/leven/logboek.jsonl"


def _geheim():
    with open("/home/arch/.amber-geheim") as f:
        return f.read().strip()


def ssh(opdracht):
    r = subprocess.run(["sshpass", "-p", _geheim(), "ssh",
                        "-o", "ConnectTimeout=8", TRAINER, opdracht],
                       capture_output=True, text=True)
    return r.returncode == 0, r.stdout.strip()


# 1. alleen op een rungrens
ok, dienst = ssh("systemctl is-active amber-train")
if not ok:
    sys.exit("trainer onbereikbaar — niets bezorgd")
if dienst == "active":
    sys.exit("de run draait — het logboek heeft één schrijver; "
             "bezorg op een rungrens")

# 2. wat ligt er te wachten?
try:
    regels = [json.loads(r) for r in open(BRIEVENBUS)]
except FileNotFoundError:
    sys.exit("de brievenbus is leeg (bestaat nog niet)")
post = [r for r in regels if not r.get("bezorgd")]
if not post:
    sys.exit("niets onbezorgds in de brievenbus")

# 3. het regelnummer en de stap waar zij is
ok, staart = ssh(f"tail -1 {LOGBOEK}")
if not ok or not staart:
    sys.exit("kan het logboek niet lezen — niets bezorgd")
laatste = json.loads(staart)
nr = int(laatste.get("nr", 0))
stap = int(laatste.get("stap") or 0)

# 4. bezorgen, in één ssh-schrijfslag, met fsync via een tijdelijk pad
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
        # Het oog (Qwen2.5-VL op kaart 1) zag een foto van een rit en
        # beschreef hem in het Nederlands. De beschrijving is de
        # waarneming; de foto zelf blijft in fase2/beelden/.
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
blok = "\n".join(nieuwe) + "\n"
ok, _ = ssh("cat >> " + LOGBOEK + " << 'POST'\n" + blok + "POST\nsync")
if not ok:
    sys.exit("bezorgen mislukte — brievenbus blijft ongemoeid")

# 5. afvinken (atomair herschrijven)
for r in regels:
    r["bezorgd"] = True
with open(BRIEVENBUS + ".deel", "w") as f:
    for r in regels:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
os.replace(BRIEVENBUS + ".deel", BRIEVENBUS)
print(f"bezorgd: {len(post)} waarneming(en), logboek t/m regel {nr}, "
      f"bij stap {stap}")
