"""
Toetst het checkpointformaat.

Het meetpunt van fase 1, maar dan nu al op het mechanisme: honderd stappen,
onderbroken door een échte procesdood, moeten bit voor bit hetzelfde uitkomen
als honderd stappen achter elkaar.

En de tweede eis erbij: het bestand moet leesbaar zijn op een machine zonder
deze kaarten. Dat wordt hier nagebootst door de kaarten onzichtbaar te maken.

Draaien:  venv/bin/python kern/toets-checkpoint.py
"""

import determinisme                       # MOET vóór torch
determinisme.zet_vast(1)

import json
import os
import subprocess
import sys

import torch

import checkpoint

HIER = os.path.dirname(os.path.abspath(__file__))
MAP = "/home/arch/amber-werk/tmp"
PAD = f"{MAP}/toets-checkpoint.pt"
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


def werker(modus, verberg_kaarten=False):
    omgeving = dict(os.environ)
    if verberg_kaarten:
        omgeving["CUDA_VISIBLE_DEVICES"] = ""
    r = subprocess.run([PYTHON, "werker.py", modus], cwd=HIER,
                       capture_output=True, text=True, env=omgeving)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit(f"werker {modus} mislukte")
    return json.loads(r.stdout.strip().splitlines()[-1])


os.makedirs(MAP, exist_ok=True)
if os.path.exists(PAD):
    os.remove(PAD)

print("=" * 70)
print("Toets — checkpoints")
print("=" * 70)
print()

# --- 1. Onderbreken en hervatten -------------------------------------------

print("--- Honderd stappen, met een procesdood erin ---")
print("  (elke run is een eigen proces; 'herstarten' is hier echt herstarten)")
print()

heel = werker("doorlopen")
eerst = werker("deel1")           # 0..50, schrijft checkpoint, sterft
daarna = werker("deel2")          # nieuw proces, leest checkpoint, 50..100

toets("het checkpoint is aangemaakt", os.path.exists(PAD))
toets(
    "de eerste helft komt overeen met dezelfde stappen uit de hele run",
    heel["verliezen"][:50] == eerst["verliezen"],
)
toets(
    "de tweede helft ná de procesdood komt bit voor bit overeen",
    heel["verliezen"][50:] == daarna["verliezen"],
    "dit is het meetpunt van fase 1, op het mechanisme",
)
toets(
    "de eindgewichten zijn identiek",
    heel["vingerafdruk"] == daarna["vingerafdruk"],
    f"{heel['vingerafdruk'][:16]}… tegenover {daarna['vingerafdruk'][:16]}…",
)

print()

# --- 2. Hardware-onafhankelijk ---------------------------------------------

print("--- Draagbaarheid ---")

inhoud = checkpoint.lees(PAD, apparaat="cpu")
toets("laat zich lezen naar de CPU", inhoud["stap"] == 50)

apparaten = set()


def zoek_apparaten(x):
    if torch.is_tensor(x):
        apparaten.add(str(x.device))
    elif isinstance(x, dict):
        for v in x.values():
            zoek_apparaten(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            zoek_apparaten(v)


zoek_apparaten({k: v for k, v in inhoud.items() if k != "machine"})
toets(
    "er staat geen enkele tensor met een kaart-apparaat in het bestand",
    apparaten <= {"cpu"},
    f"gevonden apparaten: {apparaten or '{}'}",
)

# De echte proef: een proces dat de kaarten helemaal niet ziet.
zonder = werker("deel2", verberg_kaarten=True)
toets(
    "een proces zónder zichtbare kaarten kan het checkpoint gebruiken",
    zonder["van"] == 50,
    "zo overleeft toestand een GPU-upgrade: verhuizen in plaats van opnieuw beginnen",
)

toets(
    "wat er over de machine in staat is puur ter informatie",
    "kaarten" in inhoud["machine"] and inhoud["determinisme"]["zaad"] == 1234,
    f"kaarten in het bestand: {inhoud['machine']['kaarten']}",
)

print()

# --- 3. Bestand tegen onderbreking en beschadiging --------------------------

print("--- Bestand tegen stroomverlies ---")

toets(
    "er blijft geen half bestand achter",
    not os.path.exists(PAD + ".deel"),
    "geschreven naar .deel, gefsynct, dan pas atomair hernoemd",
)

# Eén byte omzetten moet opvallen bij het lezen, niet weken later in de metingen.
with open(PAD, "r+b") as f:
    f.seek(os.path.getsize(PAD) - 20)
    b = f.read(1)
    f.seek(os.path.getsize(PAD) - 20)
    f.write(bytes([b[0] ^ 0xFF]))

try:
    checkpoint.lees(PAD)
    betrapt = False
except Exception as e:
    betrapt = "beschadigd" in str(e)
toets("een omgezette byte wordt betrapt door het controlegetal", betrapt,
      "op deze machine is dat geen luxe: geen batterij op de controller, "
      "en de bootschijf heeft geen power-loss protection")

os.remove(PAD)

print()
print("=" * 70)
print(f"geslaagd: {geslaagd}    gefaald: {gefaald}")
print("=" * 70)
sys.exit(0 if gefaald == 0 else 1)
