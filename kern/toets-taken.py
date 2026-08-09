"""
Toetst de meetopstelling.

Twee soorten controle, en de tweede is de belangrijkste:

  * doet de opzet wat hij belooft — reproduceerbaar, afgeschermd, geordend
  * **klopt het antwoord eigenlijk wel?** De opgaven worden hier onafhankelijk
    nagerekend: rekensommen met eval, codeopgaven door het programma echt uit
    te voeren en de uitvoer te vergelijken. Zonder dat toets je alleen of de
    generator consequent is met zichzelf, en dat is een generator die stelselmatig
    verkeerde antwoorden geeft ook

Draaien:  venv/bin/python kern/toets-taken.py
"""

import io
import contextlib
import re
import sys

import taken

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
print("Toets — de meetopstelling")
print("=" * 70)
print()

# --- 1. Kloppen de antwoorden? ---------------------------------------------

print("--- Zijn de opgaven goed nagerekend? ---")

fout = []
for graad in taken.GRADEN:
    for n in range(200):
        t = taken.maak("rekenen", graad, n)
        if str(eval(t.opgave)) != t.oplossing:
            fout.append((t.opgave, t.oplossing, eval(t.opgave)))
toets("1000 rekensommen komen overeen met wat Python zelf uitrekent",
      not fout, f"{len(fout)} afwijkingen" if fout else "geen enkele afwijking")

fout = []
for graad in taken.GRADEN:
    for n in range(60):
        t = taken.maak("code", graad, n)
        uit = io.StringIO()
        with contextlib.redirect_stdout(uit):
            exec(t.opgave, {})
        if uit.getvalue().strip() != t.oplossing:
            fout.append((t.opgave, t.oplossing, uit.getvalue().strip()))
toets(
    "300 codeopgaven drukken werkelijk af wat als antwoord genoteerd staat",
    not fout,
    f"{len(fout)} afwijkingen" if fout else "elk programma echt uitgevoerd",
)

# Bij de puzzels is er geen tweede bron van waarheid, dus daar wordt de regel
# zelf nagelopen op de reeks zoals hij getoond wordt.
fout = []
for n in range(200):
    t = taken.maak("puzzel", 1, n)
    rij = [int(x) for x in re.findall(r"-?\d+", t.opgave)]
    verschillen = {rij[i + 1] - rij[i] for i in range(len(rij) - 1)}
    if len(verschillen) != 1 or int(t.oplossing) != rij[-1] + verschillen.pop():
        fout.append(t.opgave)
toets("de rijen van graad 1 hebben werkelijk een vast verschil", not fout)

fout = []
for n in range(200):
    t = taken.maak("puzzel", 5, n)
    rij = [int(x) for x in re.findall(r"-?\d+", t.opgave)]
    if any(rij[i] + rij[i + 1] != rij[i + 2] for i in range(len(rij) - 2)):
        fout.append(t.opgave)
    elif int(t.oplossing) != rij[-1] + rij[-2]:
        fout.append(t.opgave)
toets("de rijen van graad 5 zijn werkelijk de som van de twee ervoor", not fout)

print()

# --- 2. Reproduceerbaar ----------------------------------------------------

print("--- Reproduceerbaar ---")
toets("dezelfde drie argumenten geven dezelfde taak",
      taken.maak("rekenen", 3, 4242) == taken.maak("rekenen", 3, 4242))
toets("een ander nummer geeft een andere taak",
      taken.maak("rekenen", 3, 4242) != taken.maak("rekenen", 3, 4243))
toets("dezelfde graad in een andere familie geeft iets anders",
      taken.maak("code", 2, 5).opgave != taken.maak("puzzel", 2, 5).opgave)

# Het taakuniversum mag niet meebewegen met het zaad van een leerrun, anders
# kun je twee runs niet meer met elkaar vergelijken.
import determinisme                                    # noqa: E402
vooraf = taken.maak("rekenen", 4, 5000).opgave
determinisme.zet_vast(999_999)
achteraf = taken.maak("rekenen", 4, 5000).opgave
toets(
    "de taken veranderen niet als het leerzaad verandert",
    vooraf == achteraf,
    "anders weet je bij een verschil tussen twee runs niet of het aan het "
    "leren lag of aan andere sommen",
)

print()

# --- 3. De meetlat is afgeschermd ------------------------------------------

print("--- De meetlat ---")
try:
    taken.leertaak("rekenen", 1, taken.TEST_TOT - 1)
    geweigerd = False
except ValueError as e:
    geweigerd = "meetlat" in str(e)
toets("leren van een meetlatnummer wordt geweigerd", geweigerd,
      "besmetting is hiermee een programmeerfout, geen kwestie van discipline")

# Afschermen op nummer alleen is niet genoeg: dezelfde opgave kan onder een
# leernummer én onder een meetlatnummer opduiken.
teksten = taken._meetlat_van("rekenen", 1)
botsers = [n for n in range(taken.TEST_TOT, taken.TEST_TOT + 3000)
           if taken.maak("rekenen", 1, n).opgave in teksten]
toets(
    "opgaven botsen werkelijk over de nummergrens heen",
    len(botsers) > 0,
    f"{len(botsers)} van de 3000 leernummers geven een opgave die ook in de "
    f"meetlat staat — afschermen op nummer alleen zou dus niet genoeg zijn",
)

try:
    taken.leertaak("rekenen", 1, botsers[0])
    geweigerd = False
except ValueError as e:
    geweigerd = "opgave staat er wél in" in str(e)
toets("zo'n botsing wordt óók geweigerd, op inhoud", geweigerd)

reeks = taken.leerreeks("rekenen", 1, 300)
toets(
    "leerreeks levert alleen schone taken",
    not any(taken.is_besmet(t) for t in reeks) and len(reeks) == 300,
    "besmette nummers worden overgeslagen in plaats van meegeleverd",
)

toets("het eerste toegestane leernummer werkt wel",
      taken.leertaak("rekenen", 1, taken.TEST_TOT).nummer == taken.TEST_TOT)

meetlat = {t.nummer for t in taken.testverzameling("code", 3, 100)}
leren = {t.nummer for t in taken.leerreeks("code", 3, 100)}
toets("meetlat en leertaken overlappen nergens", not (meetlat & leren),
      f"meetlat 0–{max(meetlat)}, leren {min(leren)}–{max(leren)}")

toets("de meetlat is elke keer dezelfde, in dezelfde volgorde",
      [t.opgave for t in taken.testverzameling("puzzel", 2, 50)]
      == [t.opgave for t in taken.testverzameling("puzzel", 2, 50)])

print()

# --- 4. Nakijken -----------------------------------------------------------

print("--- Nakijken ---")
t = taken.maak("rekenen", 1, 7)
toets("het juiste antwoord wordt goedgekeurd", t.nakijk(t.oplossing))
toets("spaties eromheen maken niet uit", t.nakijk(f"  {t.oplossing} "))
toets("een fout antwoord wordt afgekeurd", not t.nakijk("999999"))
toets("bijna goed is fout", not t.nakijk(str(int(t.oplossing) + 1)),
      "een score die van een oordeel afhangt is geen meting")

print()

# --- 5. Loopt de moeilijkheid op? ------------------------------------------
# Een botte vuistregel — tel alle getallen in de opgave bij elkaar op — hoort
# het goed te doen op graad 1 en te verdrinken daarboven. Dat laat zien dat de
# graden werkelijk iets anders vragen en niet alleen groter zijn.

print("--- Loopt de moeilijkheid op? ---")
print("  Een vuistregel die alleen kan optellen, losgelaten op elke graad.")
print("  Let op wat dit wel en niet aantoont — zie de toelichting eronder.")
print()


def vuistregel(opgave):
    return sum(int(x) for x in re.findall(r"-?\d+", opgave))


scores = []
for graad in taken.GRADEN:
    proef = [taken.maak("rekenen", graad, n) for n in range(200)]
    goed = sum(1 for t in proef if t.nakijk(vuistregel(t.opgave)))
    scores.append(goed / len(proef))
    print(f"         graad {graad}: vuistregel haalt {goed / len(proef):>5.0%}")

toets(
    "alleen kunnen optellen brengt je tot en met graad 2, en niet verder",
    min(scores[:2]) > 0.3 and max(scores[2:]) < 0.1,
    "vanaf graad 3 is een andere bewerking nodig; vanaf 4 meerdere achter elkaar",
)

print()
print("         Wat dit NIET aantoont: dat de graden strikt oplopen. Graad 2")
print("         scoort hier hoger dan graad 1, en graad 3 is één vermenigvuldiging")
print("         tegenover één optelling — een andere bewerking, geen zwaardere.")
print("         Voor C is dat genoeg: de graden moeten stabiel en onderling te")
print("         onderscheiden zijn, niet perfect geijkt.")

print()

# --- 6. Hoe groot is elke voorraad? ----------------------------------------
# Belangrijk om te weten vóór fase 1: is de voorraad klein, dan leert ze hem uit
# het hoofd en meet je geheugen in plaats van kunnen.

print("--- Hoe veel verschillende taken bestaan er? ---")
krap = []
for familie in taken.FAMILIES:
    regel = []
    for graad in taken.GRADEN:
        uniek = len({taken.maak(familie, graad, n).opgave for n in range(3000)})
        regel.append(uniek)
        if uniek < 500:
            krap.append((familie, graad, uniek))
    print(f"         {familie:8} " + "  ".join(f"g{g}:{u:>5}"
                                               for g, u in zip(taken.GRADEN, regel)))

print()
if krap:
    print("         KRAP — hier kan ze de voorraad uit het hoofd leren:")
    for familie, graad, uniek in krap:
        print(f"           {familie} graad {graad}: {uniek} verschillende opgaven")
    print("         Dat is geen fout, maar wel iets om te weten: op zo'n graad")
    print("         meet je op den duur geheugen en geen kunnen.")

toets("elke familie heeft op de hoogste graad een ruime voorraad",
      all(len({taken.maak(f, 5, n).opgave for n in range(3000)}) > 1000
          for f in taken.FAMILIES))

print()
print("=" * 70)
print(f"geslaagd: {geslaagd}    gefaald: {gefaald}")
print("=" * 70)
sys.exit(0 if gefaald == 0 else 1)
