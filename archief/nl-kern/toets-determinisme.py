"""
Toetst de determinismemodule.

Niet "draait het", maar: doet de grendel wat hij belooft, en klopt de aanname
waar het hele checkpointformaat op rust — dat hervatten vanaf stap N dezelfde
reeks geeft als doorlopen tot N.

Draaien:  venv/bin/python kern/toets-determinisme.py
"""

import determinisme            # MOET vóór torch — de module bewaakt dat zelf

import subprocess
import sys

import torch

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


print("=" * 70)
print("Toets — determinisme")
print("=" * 70)
print()

# --- 1. De grendel ---------------------------------------------------------
# De module moet weigeren als torch al geladen is, want dan heeft
# CUBLAS_WORKSPACE_CONFIG geen effect meer en is determinisme stil half uit.

print("--- De grendel ---")
r = subprocess.run(
    [sys.executable, "-c", "import torch; import determinisme"],
    capture_output=True, text=True, cwd="/home/arch/amber-werk/kern",
    env={"PATH": "/usr/bin"},
)
toets(
    "import ná torch wordt geweigerd",
    r.returncode != 0 and "nádat torch al geladen was" in r.stderr,
    "de module laat zich niet stilzwijgend te laat laden",
)

print()

# --- 2. Aanzetten en terugcontroleren --------------------------------------

print("--- Aanzetten ---")
stand = determinisme.zet_vast(1234)
toets("zet_vast() komt door de eigen controle", True)
toets(
    "deterministische algoritmen staan aan",
    stand["deterministische_algoritmen"] is True,
)
toets("cudnn.benchmark staat uit", stand["cudnn_benchmark"] is False,
      "die kiest anders per run een ander algoritme")
toets("CUBLAS_WORKSPACE_CONFIG staat goed",
      stand["cublas_werkruimte"] == ":4096:8")

# De controle moet ook echt aanslaan als iemand het later uitzet.
torch.backends.cudnn.benchmark = True
try:
    determinisme.controleer()
    betrapt = False
except RuntimeError:
    betrapt = True
finally:
    torch.backends.cudnn.benchmark = False
toets("controleer() betrapt een instelling die later wordt omgezet", betrapt,
      "een grendel die niet klemt is geen grendel")

print()

# --- 3. De afleiding is draagbaar ------------------------------------------

print("--- De afleiding ---")
a = determinisme.zaad_voor_stap(7)
b = determinisme.zaad_voor_stap(7)
toets("hetzelfde stapnummer geeft hetzelfde zaad", a == b)
toets("verschillende stappen geven verschillende zaden",
      determinisme.zaad_voor_stap(7) != determinisme.zaad_voor_stap(8))
toets("het zaad past binnen wat torch accepteert", 0 <= a < 2**63)
zaden = {determinisme.zaad_voor_stap(i) for i in range(2000)}
toets("2000 opeenvolgende stappen geven 2000 verschillende zaden",
      len(zaden) == 2000, f"{len(zaden)} unieke waarden")

print()

# --- 4. Waar het om draait: hervatten ~ doorlopen --------------------------
# Dit is de aanname waar het hele checkpointformaat op rust. Klopt hij niet,
# dan is (zaad, stapnummer) niet genoeg en moet er alsnog generatortoestand
# mee — precies wat we niet willen.

print("--- Hervatten tegenover doorlopen ---")

apparaat = "cuda" if torch.cuda.is_available() else "cpu"


def reeks(stappen, vanaf=0):
    """Bootst een leerlus na: elke stap trekt toeval en rekent ermee."""
    uit = []
    for stap in range(vanaf, stappen):
        determinisme.begin_stap(stap)
        x = torch.randn(64, 64, device=apparaat)
        laag = torch.nn.Linear(64, 64).to(apparaat)
        y = (laag(x).relu() * torch.randn(64, 64, device=apparaat)).sum()
        uit.append(y.detach().clone())
    return uit


doorlopen = reeks(10)
opnieuw = reeks(10)
toets("twee volledige runs zijn bit voor bit gelijk",
      all(torch.equal(p, q) for p, q in zip(doorlopen, opnieuw)))

hervat = reeks(10, vanaf=5)
toets(
    "hervatten vanaf stap 5 geeft exact wat doorlopen daar gaf",
    all(torch.equal(p, q) for p, q in zip(doorlopen[5:], hervat)),
    "hierop rust de keuze om alleen (zaad, stapnummer) te bewaren "
    "in plaats van kaartspecifieke generatortoestand",
)

# En een ander zaad moet wél iets anders geven, anders bewijst het bovenstaande niets.
determinisme.zet_vast(9999)
anders = reeks(3)
determinisme.zet_vast(1234)
toets("een ander zaad geeft een andere reeks",
      not any(torch.equal(p, q) for p, q in zip(doorlopen[:3], anders)))

print()

# --- 5. Wat er in het checkpoint gaat --------------------------------------

print("--- De stand die het checkpoint in gaat ---")
s = determinisme.stand()
toets("bevat alleen getallen, tekst en waarheidswaarden",
      all(isinstance(v, (int, str, bool, type(None))) for v in s.values()),
      "niets apparaatgebonden, anders is het checkpoint niet draagbaar")
for k, v in s.items():
    print(f"         {k}: {v}")

print()
print("=" * 70)
print(f"geslaagd: {geslaagd}    gefaald: {gefaald}")
print("=" * 70)
sys.exit(0 if gefaald == 0 else 1)
