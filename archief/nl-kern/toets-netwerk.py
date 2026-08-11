"""
Toetst de tekenset en de leerkern.

Twee eigenschappen wegen hier het zwaarst, en allebei zijn ze later niet meer
in te bouwen:

  * **groeien verandert de uitvoer niet** — bit voor bit, niet ongeveer
  * de tekenset en de posities liggen vast op een manier die niet herzien hoeft

Draaien:  venv/bin/python kern/toets-netwerk.py
"""

import determinisme                        # MOET vóór torch
determinisme.zet_vast(1234)

import sys

import torch

import netwerk
import taken
import tekens

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
print("Toets — tekenset en leerkern")
print("=" * 70)
print()

# --- 1. De tekenset --------------------------------------------------------

print("--- De tekenset ---")
toets("tekst gaat er heen en weer doorheen",
      tekens.decodeer(tekens.codeer("47 * 13")) == "47 * 13")
toets("Nederlands met accenten past er zonder meer in",
      tekens.decodeer(tekens.codeer("één café, zéér véél")) == "één café, zéér véél",
      "bytes hoeven nooit uitgebreid te worden")
toets("cijfers blijven losse tekens",
      len(tekens.codeer("47")) == 2,
      "geen tokenizer die '47' tot één brok plakt — dat maakt rekenen "
      "kunstmatig moeilijk")

t = taken.maak("rekenen", 3, 5)
reeks, telt_mee = tekens.taak_naar_reeks(t)
toets("een taak wordt VRAAG opgave ANTWOORD oplossing EIND",
      reeks[0] == tekens.VRAAG and tekens.ANTWOORD in reeks
      and reeks[-1] == tekens.EIND,
      tekens.toon(reeks))

gemarkeerd = [c for c, m in zip(reeks, telt_mee) if m]
toets(
    "de fout telt alleen over het antwoord en het EIND-teken",
    tekens.decodeer(gemarkeerd) == t.oplossing and gemarkeerd[-1] == tekens.EIND
    and not any(telt_mee[:reeks.index(tekens.ANTWOORD) + 1]),
    "anders leert ze vragen verzinnen in plaats van beantwoorden",
)

toets("het antwoord is er weer uit te halen",
      tekens.antwoord_uit_reeks(reeks) == t.oplossing)
toets("uit een half antwoord komt niets", tekens.antwoord_uit_reeks([1, 2, 3]) == "",
      "liever leeg dan half")

reeksen, maskers = tekens.bundel([[1, 2, 3], [1, 2]], [[True] * 3, [True] * 2])
toets("opvulling telt nergens in mee",
      reeksen[1][-1] == tekens.VUL and maskers[1][-1] is False,
      "anders leert ze opvulling voorspellen en ziet de fout er goed uit")

print()

# --- 2. Het netwerk draait -------------------------------------------------

print("--- Het netwerk ---")
kern = netwerk.Kern(lagen=4, breedte=128, koppen=4, venster=64)
codes = torch.randint(0, 255, (2, 32))
uit = kern(codes)
toets("de uitvoer heeft de goede vorm",
      tuple(uit.shape) == (2, 32, tekens.OMVANG),
      f"{tuple(uit.shape)} — één score per teken van de tekenset")

toets("het aantal parameters wordt geteld",
      kern.aantal_parameters() > 0,
      f"{kern.aantal_parameters():,} in deze kleine proefopstelling")

# Causaal: een teken mag niet naar de toekomst kijken. Verander het laatste
# teken en alles daarvóór moet exact gelijk blijven.
a = codes.clone()
b = codes.clone()
b[:, -1] = (b[:, -1] + 7) % 255
uit_a, uit_b = kern(a), kern(b)
toets(
    "een teken kijkt nooit vooruit",
    torch.equal(uit_a[:, :-1], uit_b[:, :-1]),
    "het laatste teken veranderen laat alles daarvóór bit voor bit gelijk",
)

print()

# --- 3. Waar het om gaat: groeien verandert niets --------------------------

print("--- Groeien ---")
kern = netwerk.Kern(lagen=4, breedte=128, koppen=4, venster=64)
kern.eval()
codes = torch.randint(0, 255, (2, 32))
with torch.no_grad():
    voor = kern(codes).clone()

vorm_voor = kern.vorm()
kern.voeg_blok_toe()
with torch.no_grad():
    na = kern(codes)

toets(
    "een laag erbij laat de uitvoer BIT VOOR BIT gelijk",
    torch.equal(voor, na),
    "geen benadering: x + 0 * iets is exact x. Zonder dit meet je bij E "
    "geen groei maar schade",
)
toets("en er is werkelijk een laag bij gekomen",
      kern.vorm()["lagen"] == vorm_voor["lagen"] + 1
      and kern.aantal_parameters() > vorm_voor["parameters"],
      f"{vorm_voor['lagen']} → {kern.vorm()['lagen']} lagen, "
      f"{vorm_voor['parameters']:,} → {kern.aantal_parameters():,} parameters")

# Ook middenin invoegen mag niets veranderen.
kern.voeg_blok_toe(positie=1)
with torch.no_grad():
    na_midden = kern(codes)
toets("ook een laag middenin verandert niets", torch.equal(voor, na_midden))

# En het nieuwe blok moet wél kunnen gaan meedoen.
nieuw = kern.blokken[1]
with torch.no_grad():
    nieuw.alfa1.fill_(0.1)
with torch.no_grad():
    na_aanzetten = kern(codes)
toets("zodra de weegfactor van nul af komt, doet het blok mee",
      not torch.equal(voor, na_aanzetten),
      "het blok ligt niet dood, het staat op nul en leert zich in")

print()

# --- 4. Herhaalbaar --------------------------------------------------------

print("--- Herhaalbaar ---")
determinisme.zet_vast(4242)
k1 = netwerk.Kern(lagen=2, breedte=64, koppen=2, venster=32)
determinisme.zet_vast(4242)
k2 = netwerk.Kern(lagen=2, breedte=64, koppen=2, venster=32)
gelijk = all(torch.equal(a, b) for a, b in zip(k1.parameters(), k2.parameters()))
toets("hetzelfde zaad geeft hetzelfde netwerk", gelijk)

codes = torch.randint(0, 255, (1, 16))
k1.eval()
with torch.no_grad():
    toets("tweemaal dezelfde invoer geeft bit voor bit dezelfde uitvoer",
          torch.equal(k1(codes), k1(codes)))

# Achterwaarts moet het ook herhaalbaar zijn, anders is de leerlus het niet.
def gradient():
    determinisme.zet_vast(77)
    k = netwerk.Kern(lagen=2, breedte=64, koppen=2, venster=32)
    determinisme.begin_stap(5)
    c = torch.randint(0, 255, (2, 16))
    k(c).square().mean().backward()
    return [p.grad.clone() for p in k.parameters()]

toets("de achterwaartse stap is ook herhaalbaar",
      all(torch.equal(a, b) for a, b in zip(gradient(), gradient())),
      "met de hand uitgeschreven aandacht, juist hierom")

print()

# --- 5. De vorm gaat mee ---------------------------------------------------

print("--- De vorm ---")
kern = netwerk.Kern(lagen=3, breedte=64, koppen=2, venster=32)
kern.voeg_blok_toe()
opnieuw = netwerk.Kern.uit_vorm(kern.vorm())
toets(
    "uit de vorm is hetzelfde netwerk opnieuw op te bouwen",
    opnieuw.vorm()["lagen"] == 4
    and opnieuw.aantal_parameters() == kern.aantal_parameters(),
    "zonder de vorm in het checkpoint weet je na groei niet meer hoeveel "
    "lagen erin zaten",
)

print()

# --- 6. Op ware grootte ----------------------------------------------------

print("--- Op ware grootte ---")
groot = netwerk.Kern()
v = groot.vorm()
print(f"         {v['lagen']} lagen, breedte {v['breedte']}, {v['koppen']} koppen, "
      f"venster {v['venster']}")
print(f"         {v['parameters']:,} parameters "
      f"({v['parameters'] * 16 / 1024**2:.0f} MB aan gewichten, gradiënten en "
      f"optimizertoestand)")
toets("de voorgestelde maat is wat hij hoort te zijn",
      10_000_000 < v["parameters"] < 25_000_000)

print()
print("=" * 70)
print(f"geslaagd: {geslaagd}    gefaald: {gefaald}")
print("=" * 70)
sys.exit(0 if gefaald == 0 else 1)
