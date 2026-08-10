"""
Toetst de sleutelbrug — overleeft haar brein de Engelse hernoeming?

De zwaarste toets loopt op haar échte checkpoint als dat er staat
(fase1/nu.pt, door de kijker ververst): Nederlandse kern en Engelse kern,
zelfde gewichten via de brug, zelfde invoer — en de uitvoer moet bit voor
bit gelijk zijn. Staat er geen checkpoint (bv. op een verse machine), dan
geldt dezelfde eis op verse gewichten.

Draaien:  venv/bin/python kern/toets-sleutelbrug.py
"""

import determinisme                        # MOET vóór torch
determinisme.zet_vast(1234)

import os
import sys

import torch

import bridge
import checkpoint
import netwerk
import network

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
print("Toets — sleutelbrug (Nederlands checkpoint -> Engelse kern)")
print("=" * 70)
print()

# --- 1. Op verse gewichten -------------------------------------------------

print("--- Verse gewichten ---")
nl = netwerk.Kern(lagen=3, breedte=96, koppen=4, venster=128)
nl.eval()
en = network.Core.from_spec(bridge.translate_spec(nl.vorm()))
ontbreekt = en.load_state_dict(bridge.translate_state(nl.state_dict()),
                               strict=True)
toets("elke Nederlandse sleutel vindt zijn Engelse plek", True,
      "load_state_dict strict=True zou anders geweigerd hebben")

determinisme.begin_stap(1)
invoer = torch.randint(0, 260, (3, 128))
with torch.no_grad():
    uit_nl = nl.vooruit(invoer)[0]
    uit_en = en.advance(invoer)[0]
toets("zelfde invoer, zelfde uitvoer, bit voor bit",
      torch.equal(uit_nl, uit_en))

toets("Engelse invoer gaat ongemoeid door de brug",
      bridge.translate_state(en.state_dict()) is not None
      and not bridge.is_dutch_state(en.state_dict()))

# --- 2. Met cache en masker, zoals bij het antwoorden ----------------------

print()
print("--- Antwoordweg: cache en masker ---")
with torch.no_grad():
    _, cache_nl = nl.vooruit(invoer[:, :100])
    _, cache_en = en.advance(invoer[:, :100])
    stap_nl = nl.vooruit(invoer[:, 100:101], cache=cache_nl, vanaf=100)[0]
    stap_en = en.advance(invoer[:, 100:101], cache=cache_en, offset=100)[0]
toets("één teken schrijven tegen een gevulde cache: gelijk",
      torch.equal(stap_nl, stap_en))

masker = torch.zeros(3, 128, dtype=torch.bool)
masker[:, :7] = True                       # links opgevuld, zoals echt
with torch.no_grad():
    m_nl = nl.vooruit(invoer, sleutelmasker=masker)[0]
    m_en = en.advance(invoer, key_mask=masker)[0]
toets("met opvulmasker: gelijk", torch.equal(m_nl, m_en))

# --- 3. Op haar echte checkpoint, als het er staat -------------------------

print()
print("--- Haar echte checkpoint ---")
PAD = "/home/arch/amber-werk/fase1/nu.pt"
if os.path.exists(PAD):
    inhoud = checkpoint.lees(PAD)
    vorm = (inhoud.get("extra") or {}).get("vorm") or {
        "lagen": 8, "breedte": 384, "koppen": 6, "venster": 512}
    echt_nl = netwerk.Kern.uit_vorm(vorm)
    checkpoint.herstel(inhoud, echt_nl, None)
    echt_nl.eval()

    echt_en = network.Core.from_spec(bridge.translate_spec(vorm))
    echt_en.load_state_dict(bridge.translate_state(echt_nl.state_dict()),
                            strict=True)
    echt_en.eval()

    determinisme.begin_stap(2)
    proef = torch.randint(0, 260, (2, 512))
    with torch.no_grad():
        e_nl = echt_nl.vooruit(proef)[0]
        e_en = echt_en.advance(proef)[0]
    toets("haar run-3-gewichten geven door de brug identieke uitvoer",
          torch.equal(e_nl, e_en),
          f"checkpoint van stap {inhoud.get('stap', '?')}, vol venster")
    toets("en de Engelse kern kan daarna gewoon groeien",
          (echt_en.grow_window(768) or echt_en.window == 768))
else:
    print("         (geen checkpoint gevonden — overgeslagen)")

print()
print("=" * 70)
print(f"geslaagd: {geslaagd}    gefaald: {gefaald}")
print("=" * 70)
sys.exit(0 if gefaald == 0 else 1)
