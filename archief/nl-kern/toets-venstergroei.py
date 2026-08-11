"""
Toetst het groeien van het venster — de kern van fase 2.

De belofte die hier wordt afgedwongen: een groter venster verandert níéts aan
wat ze al is. Zelfde invoer, zelfde uitvoer, bit voor bit — en haar checkpoint
van vóór de groei verhuist mee zonder één parameter te verliezen. Dit is
waarom de posities via draaiing gaan en niet via een geleerde tabel: een tabel
had hier nieuwe, ongetrainde parameters betekend en dus een andere Amber.

Draaien:  venv/bin/python kern/toets-venstergroei.py
"""

import determinisme                        # MOET vóór torch
determinisme.zet_vast(1234)

import os
import sys
import tempfile

import torch

import checkpoint
import netwerk

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
print("Toets — venstergroei")
print("=" * 70)
print()

# Klein netwerk is genoeg: de eigenschap hangt niet van de maat af.
kern = netwerk.Kern(lagen=2, breedte=64, koppen=4, venster=64)
kern.eval()

determinisme.begin_stap(1)
invoer = torch.randint(0, 260, (2, 64))    # precies het oude venster vol

with torch.no_grad():
    voor, _ = kern.vooruit(invoer)

# --- 1. Groeien verandert de uitvoer niet ---------------------------------

print("--- Groeien verandert haar niet ---")
kern.groei_venster(96)
with torch.no_grad():
    na, _ = kern.vooruit(invoer)
toets("uitvoer na groei bit voor bit gelijk", torch.equal(voor, na),
      "zelfde invoer, venster 64 -> 96")
toets("de vorm meldt het nieuwe venster", kern.vorm()["venster"] == 96)
toets("parameters ongewijzigd door groei",
      kern.vorm()["parameters"] == netwerk.Kern(
          lagen=2, breedte=64, koppen=4, venster=64).vorm()["parameters"],
      "venstergroei voegt geen parameters toe — dat is het hele punt")

# --- 2. Het nieuwe gebied is echt open ------------------------------------

print()
print("--- Het nieuwe gebied ---")
lang = torch.randint(0, 260, (1, 96))
with torch.no_grad():
    uit_lang, _ = kern.vooruit(lang)
toets("een reeks langer dan het oude venster mag nu",
      uit_lang.shape[1] == 96)

te_lang = torch.randint(0, 260, (1, 97))
try:
    kern.vooruit(te_lang)
    toets("voorbij het nieuwe venster weigert", False)
except ValueError:
    toets("voorbij het nieuwe venster weigert", True)

# --- 3. Krimpen weigert ----------------------------------------------------

print()
print("--- Krimpen ---")
try:
    kern.groei_venster(64)
    toets("krimpen weigert", False)
except ValueError:
    toets("krimpen weigert", True,
          "een kleiner venster kan meegemaakte opgaven onleesbaar maken")

# --- 4. Haar checkpoint verhuist mee --------------------------------------

print()
print("--- Het checkpoint verhuist mee ---")
oud = netwerk.Kern(lagen=2, breedte=64, koppen=4, venster=64)
oud.eval()
with torch.no_grad():
    oud_uit, _ = oud.vooruit(invoer)

with tempfile.TemporaryDirectory() as map_:
    pad = os.path.join(map_, "proef.pt")
    checkpoint.schrijf(pad, stap=7, model=oud, extra={"vorm": oud.vorm()})
    inhoud = checkpoint.lees(pad)

    nieuw = netwerk.Kern.uit_vorm(inhoud["extra"]["vorm"])
    checkpoint.herstel(inhoud, model=nieuw)
    nieuw.eval()
    nieuw.groei_venster(96)

    with torch.no_grad():
        nieuw_uit, _ = nieuw.vooruit(invoer)
    toets("geladen + gegroeid geeft dezelfde uitvoer als het origineel",
          torch.equal(oud_uit, nieuw_uit),
          "run-3-checkpoint kan run 4 in met een groter venster")
    toets("de groei komt in het volgende checkpoint terecht",
          nieuw.vorm()["venster"] == 96)

print()
print("=" * 70)
print(f"{geslaagd} geslaagd, {gefaald} gefaald")
print("=" * 70)
sys.exit(1 if gefaald else 0)
