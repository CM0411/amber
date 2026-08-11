"""
Toetst het logboek.

De belofte uit de roadmap is "verlies: seconden in plaats van uren". Dat is
alleen waar als een proces dat middenin doodvalt bij het opstarten precies
terugvindt waar het was — én weet dát het is omgevallen.

Draaien:  venv/bin/python kern/toets-logboek.py
"""

import json
import os
import shutil
import subprocess
import sys
import time

import logboek

HIER = os.path.dirname(os.path.abspath(__file__))
MAP = "/home/arch/amber-werk/tmp/logboektoets"
PYTHON = sys.executable

geslaagd = 0
gefaald = 0


def toets(naam, goed, toelichting=""):
    global geslaagd, gefaald
    if goed:
        geslaagd += 1
        print(f"[  OK  ] {naam}")
    else:
        gefaald += 1
        print(f"[ FOUT ] {naam}")
    if toelichting:
        print(f"         {toelichting}")


def werker(modus, verwacht_dood=False):
    r = subprocess.run([PYTHON, "werker-logboek.py", modus], cwd=HIER,
                       capture_output=True, text=True)
    if verwacht_dood:
        return r
    if r.returncode != 0:
        print(r.stderr[-1500:])
        raise SystemExit(f"werker {modus} mislukte")
    return json.loads(r.stdout.strip().splitlines()[-1])


shutil.rmtree(MAP, ignore_errors=True)

print("=" * 70)
print("Toets — het logboek")
print("=" * 70)
print()

# --- 1. Omvallen midden in het werk ---------------------------------------

print("--- Stroomstoring: SIGKILL op stap 87 ---")
r = werker("val_om", verwacht_dood=True)
toets("het proces is werkelijk hard gestorven",
      r.returncode == -9,
      f"afsluitcode {r.returncode} (-9 = SIGKILL, geen opruimen, geen flush)")

na = werker("hervat")
toets("de momentopname staat op stap 50", na["opname_bij"] == 50)
toets(
    "het logboek vult precies het gat tussen opname en omvallen",
    na["eerste_na_opname"] == 50 and na["laatste_na_opname"] == 87,
    f"gebeurtenissen van stap {na['eerste_na_opname']} t/m "
    f"{na['laatste_na_opname']} — verlies is nul stappen, niet 37",
)
toets(
    "het omvallen wordt herkend als incident en niet als rust",
    na["stilte"] == "incident",
    "aangekondigd afsluiten en wegvallen zijn twee verschillende dingen",
)
toets("de duur van de stilte is bekend", na["gat_gemeten"],
      "tijd als expliciete grootheid, geen ontbrekende data")
toets(
    "wat van buiten kwam is bewaard",
    na["waarnemingen"] == ["dit is niet af te leiden uit het zaad"],
    "stappen zijn herrekenbaar, waarnemingen niet — die moeten er letterlijk in",
)

print()

# --- 2. Netjes afsluiten ---------------------------------------------------

print("--- Nette afsluiting ---")
shutil.rmtree(MAP, ignore_errors=True)
werker("netjes")
na = werker("hervat")
toets("een nette afsluiting wordt herkend als rust", na["stilte"] == "rust")

print()

# --- 3. Opschonen na een momentopname --------------------------------------

print("--- Opschonen ---")
regels, _ = logboek.lees(f"{MAP}/logboek.jsonl")
stappen = [r["stap"] for r in regels if r["soort"] == "stap"]
toets(
    "regels van vóór de momentopname zijn opgeruimd",
    min(stappen) == 50,
    f"laagste stap in het logboek is {min(stappen)}, de opname staat op 50",
)
toets("er blijft geen half bestand achter",
      not os.path.exists(f"{MAP}/logboek.jsonl.deel"))

# Metingen zijn geen herstelgegevens en mogen het opschonen overleven.
proef = "/home/arch/amber-werk/tmp/blijvend"
shutil.rmtree(proef, ignore_errors=True)
log = logboek.Logboek(f"{proef}/logboek.jsonl", fsync_tussenpoos=0)
for i in range(20):
    log.schrijf("stap", stap=i, verlies="0x1.0p+0")
    if i % 10 == 0:
        log.schrijf("meting", stap=i, scores={"proef": 0.5})
log.schoon_op(15)
log.sluit()
over, _ = logboek.lees(f"{proef}/logboek.jsonl")
toets(
    "metingen overleven het opschonen, gewone stappen niet",
    len([r for r in over if r["soort"] == "meting"]) == 2
    and min(r["stap"] for r in over if r["soort"] == "stap") == 15,
    "het opschonen is er voor herstel; metingen zijn het verslag zelf. Op "
    "8 aug 2026 at het opschonen ze op en was er van een run van 1500 stappen "
    "nog één regel over",
)
shutil.rmtree(proef, ignore_errors=True)

print()

# --- 4. Een afgekapte staart ----------------------------------------------
# Dit is de vorm van beschadiging die stroomverlies oplevert: de laatste regel
# is half geschreven. Alles daarvóór moet gewoon bruikbaar blijven.

print("--- Een half geschreven laatste regel ---")
pad = f"{MAP}/logboek.jsonl"
heel, _ = logboek.lees(pad)
with open(pad, "a") as f:
    f.write('{"nr": 999, "tijd": 1.0, "soo')          # afgekapt

gehavend, stilte = logboek.lees(pad)
toets(
    "de afgekapte staart wordt weggelaten, de rest blijft leesbaar",
    len(gehavend) == len(heel),
    f"{len(gehavend)} regels teruggekregen, evenveel als vóór de beschadiging",
)

# Beschadiging middenin is iets anders: dat is geen afgekapte staart en moet
# opvallen in plaats van stilzwijgend regels weglaten.
with open(pad) as f:
    inhoud = f.read().splitlines()
inhoud[1] = "{kapot"
with open(pad, "w") as f:
    f.write("\n".join(inhoud) + "\n")
try:
    logboek.lees(pad)
    betrapt = False
except ValueError as e:
    betrapt = "beschadigd" in str(e)
toets("beschadiging middenin wordt wél gemeld", betrapt,
      "anders verlies je stilzwijgend regels en merk je het nooit")

print()

# --- 5. De prijs ------------------------------------------------------------

print("--- Wat het kost ---")
proef = "/home/arch/amber-werk/tmp/snelheid"
shutil.rmtree(proef, ignore_errors=True)

log = logboek.Logboek(f"{proef}/logboek.jsonl", fsync_tussenpoos=0)
t0 = time.perf_counter()
for i in range(200):
    log.schrijf("stap", stap=i, verlies="0x1.0p+0")
elke = (time.perf_counter() - t0) / 200 * 1000
log.sluit()

log = logboek.Logboek(f"{proef}/logboek2.jsonl", fsync_tussenpoos=1.0)
t0 = time.perf_counter()
for i in range(200):
    log.schrijf("stap", stap=i, verlies="0x1.0p+0")
soms = (time.perf_counter() - t0) / 200 * 1000
log.sluit()

grootte = os.path.getsize(f"{proef}/logboek.jsonl") / 200
print(f"         fsync na elke regel:      {elke:.3f} ms per regel")
print(f"         fsync elke seconde:       {soms:.3f} ms per regel")
print(f"         omvang:                   {grootte:.0f} bytes per regel")
toets("het logboek is goedkoop genoeg om elke stap te schrijven",
      soms < 1.0,
      "bij de standaardtussenpoos van 1 s; verlies dan hooguit die ene seconde")

shutil.rmtree(proef, ignore_errors=True)
shutil.rmtree(MAP, ignore_errors=True)

print()
print("=" * 70)
print(f"geslaagd: {geslaagd}    gefaald: {gefaald}")
print("=" * 70)
sys.exit(0 if gefaald == 0 else 1)
