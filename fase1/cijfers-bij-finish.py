"""De cijfers liggen klaar vóór Cley wakker is — na de finish van een run.

Draait als dienst op de Z490 (elke tien minuten gewekt door
amber-cijfers.timer), maar is gebouwd op de DL380 en reist met de
rungrens mee — code gaat één kant op. Zodra de run af is (dienst uit én
doel gehaald) en de kaart dus vrij, draait deze zelf de nameting per
vakje en de foutanalyse op de drie zwakste vakjes, schrijft alles naar
het rapportvak van het venster, en stuurt één melding. Zolang de run
loopt of de cijfers er al liggen doet hij níéts — de markering per
runnaam maakt hem herhaalbaar zonder herhaling.

Alles hier is lezen en meten; er verandert niets aan haar.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

RUN = json.load(open("/home/arch/rapport/run.json"))
NAAM, DOEL = RUN["naam"], int(RUN["doel"])
FASE1 = "/home/arch/amber-werk/fase1"
CHECKPOINT = f"{FASE1}/leven/momentopname.pt"
MARK = f"{FASE1}/cijfers-{NAAM}.klaar"
UIT = f"/home/arch/rapport/{NAAM}-cijfers.txt"

if os.path.exists(MARK):
    sys.exit(0)

# 1. alleen ná de finish: dienst uit én het doel gehaald
dienst = subprocess.run(["systemctl", "is-active", "amber-train"],
                        capture_output=True, text=True).stdout.strip()
if dienst == "active":
    sys.exit(0)
laatste = 0
try:
    with open(f"{FASE1}/leven/logboek.jsonl", "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - 8192))
        for regel in f.read().decode(errors="ignore").splitlines():
            try:
                r = json.loads(regel)
            except ValueError:
                continue
            if r.get("stap"):
                laatste = max(laatste, int(r["stap"]))
except FileNotFoundError:
    sys.exit(0)
if laatste < DOEL:
    sys.exit(0)


def meld(titel, tekst):
    try:
        kanaal = open("/home/arch/.amber-ntfy").read().strip()
        verzoek = urllib.request.Request(
            f"https://ntfy.sh/{kanaal}", data=tekst.encode(),
            headers={"Title": titel.encode("ascii", "ignore").decode(),
                     "Priority": "default", "Tags": "bar_chart"})
        urllib.request.urlopen(verzoek, timeout=15)
    except Exception as e:
        print("melden mislukte:", e, flush=True)


# 2. de nameting per vakje, op het eindbrein
print(f"finish gezien ({laatste:,} ≥ {DOEL:,}) — nameting begint"
      .replace(",", "."), flush=True)
nm = subprocess.run(["python3", f"{FASE1}/nameting.py", CHECKPOINT],
                    capture_output=True, text=True, timeout=3600)
delen = [f"=== nameting {NAAM} (stap {laatste:,}) ===".replace(",", "."),
         nm.stdout or nm.stderr]

if nm.returncode == 0:
    # 3. de foutanalyse op de drie zwakste vakjes uit die nameting
    scores = re.findall(r"(\w+)\s+graad (\d+):\s+(\d+)%", nm.stdout)
    zwakste = sorted(scores, key=lambda x: int(x[2]))[:3]
    vakjes = [f"{fam}:{graad}" for fam, graad, _ in zwakste]
    fa = subprocess.run(["python3", f"{FASE1}/foutanalyse.py", CHECKPOINT,
                         *vakjes], capture_output=True, text=True,
                        timeout=3600)
    delen += [f"\n=== foutanalyse zwakste vakjes: {', '.join(vakjes)} ===",
              fa.stdout or fa.stderr]

with open(UIT + ".deel", "w") as f:
    f.write("\n".join(delen))
os.replace(UIT + ".deel", UIT)

# 4. markeren en melden — de markering éérst, zodat een haperende melding
# nooit tot een tweede meetronde leidt
with open(MARK, "w") as f:
    f.write("klaar" if nm.returncode == 0 else "nameting faalde — zie "
            + UIT)

if nm.returncode == 0:
    kern = " · ".join(f"{fam} {graad}: {pct}%"
                      for fam, graad, pct in zwakste)
    meld(f"Cijfers {NAAM} klaar",
         f"nameting + foutanalyse staan klaar. Zwakste vakjes: {kern} — "
         f"lees /rapport/{NAAM}-cijfers.txt")
else:
    meld(f"Cijfers {NAAM} mislukt",
         "de nameting faalde; het verslag staat er wel — "
         f"/rapport/{NAAM}-cijfers.txt")
print("klaar", flush=True)
