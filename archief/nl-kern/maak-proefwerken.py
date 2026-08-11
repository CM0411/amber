"""
Legt de eerste drie proefwerken vast. Draait één keer.

Daarna staan ze voorgoed. Dit script weigert een bestaand proefwerk te
overschrijven, dus opnieuw draaien is ongevaarlijk — hij slaat over wat er al is.

  grondslag   de vijftien vakjes uit taken.py, elk apart. De oorspronkelijke
              meetlat, ongewijzigd overgenomen zodat alle metingen van vóór
              vandaag vergelijkbaar blijven

  gemengd     alle families en graden door elkaar op één blad. Dit ontbrak, en
              het is het punt van Cley: op een echt proefwerk staat van alles
              door elkaar, en dan moet je ook nog zien wélke soort je voor je
              hebt

  diepte      uit de grammatica, op diepte 3, 6 en 9. Stof die in taken.py
              helemaal niet voorkomt, want daar houdt het bij graad 5 op

Draaien:  venv/bin/python kern/maak-proefwerken.py
"""

import proefwerken
import taken
import wereld

PER_VAKJE = 100
GEMENGD = 300
DIEPTE = 300


def grondslag():
    uit = []
    for familie in taken.FAMILIES:
        for graad in taken.GRADEN:
            uit.extend(taken.testverzameling(familie, graad, PER_VAKJE))
    return uit


def gemengd():
    """Alle soorten door elkaar, in een vaste volgorde die niemand kan raden."""
    voorraad = []
    for familie in taken.FAMILIES:
        for graad in taken.GRADEN:
            voorraad.extend(taken.testverzameling(familie, graad, 40))
    # Eén vaste doorschudding, met een eigen trekker zodat de volgorde niets te
    # maken heeft met de volgorde waarin de taken gemaakt zijn.
    t = taken.Trekker(0x676567656E67640D)
    voorraad = list(voorraad)
    for i in range(len(voorraad) - 1, 0, -1):
        j = t.geheel(0, i)
        voorraad[i], voorraad[j] = voorraad[j], voorraad[i]
    return voorraad[:GEMENGD]


def ladder():
    """Van de bodem tot ver boven haar kunnen — zodat er op elke hoogte signaal is.

    `diepte` en `diepte2` toetsen 3, 6 en 9. Op 8 aug 2026 bleek dat te grof:
    ze zat op diepte 3 en scoorde daar 24%, en op 6 en 9 nul. Twee derde van
    dat proefwerk meet dus niets anders dan "nog niet". Een meetlat hoort
    treden te hebben waar je op staat.
    """
    uit = []
    dieptes = (1, 2, 3, 4, 5, 6)
    per_stap = 360 // (len(dieptes) * len(wereld.FAMILIES))
    for familie in wereld.FAMILIES:
        for d in dieptes:
            gevonden, nummer = [], 800_000
            while len(gevonden) < per_stap:
                taak = wereld.maak(familie, d, nummer)
                if wereld.past(taak):
                    gevonden.append(taak)
                nummer += 1
            uit.extend(gevonden)
    return uit


def diepte():
    uit = []
    per_stap = DIEPTE // (3 * len(wereld.FAMILIES))
    for familie in wereld.FAMILIES:
        for d in (3, 6, 9):
            # Nummers vanaf 900.000: ver weg van waar leerstof begint, zodat
            # botsingen zeldzaam zijn. Dat er tóch geen botsing is, bewaakt de
            # uitsluiting in wereld.leerreeks — niet dit getal.
            gevonden, nummer = [], 900_000
            while len(gevonden) < per_stap:
                taak = wereld.maak(familie, d, nummer)
                if wereld.past(taak):
                    gevonden.append(taak)
                nummer += 1
            uit.extend(gevonden)
    return uit


for naam, beschrijving, maker in (
    ("grondslag",
     "De vijftien vakjes uit taken.py, elk apart. De oorspronkelijke meetlat.",
     grondslag),
    ("gemengd",
     "Alle families en graden door elkaar op één blad. Toetst ook of ze ziet "
     "welke soort ze voor zich heeft.",
     gemengd),
    ("diepte",
     "Uit de grammatica, op diepte 3, 6 en 9. Stof die in taken.py niet "
     "voorkomt. LET OP: gemunt vóór de schrijfwijzecorrectie van 8 aug 2026, "
     "toen de wereld nog overal haakjes zette. Historisch — gebruik diepte2.",
     diepte),
    ("diepte2",
     "Uit de grammatica op diepte 3, 6 en 9, in de schrijfwijze van na "
     "8 aug 2026: haakjes alleen waar de voorrang ze vraagt, en een echte "
     "bodem op diepte 1. Vervangt diepte, dat in de oude schrijfwijze staat "
     "en daardoor onbereikbaar was.",
     diepte),
    ("ladder",
     "Uit de grammatica op diepte 1 t/m 6, twintig opgaven per familie per "
     "diepte. Fijnmaziger dan diepte2, zodat er op elke hoogte signaal is en "
     "niet twee derde van het blad alleen 'nog niet' meet.",
     ladder),
):
    if proefwerken.bestaat(naam):
        print(f"  {naam:<10} bestaat al — overgeslagen (en dat hoort zo)")
        continue
    aantal = proefwerken.vastleggen(naam, beschrijving, maker())
    print(f"  {naam:<10} vastgelegd, {aantal} opgaven")

proefwerken.vergeet_stof()
print(f"\n{len(proefwerken.namen())} proefwerken, samen "
      f"{len(proefwerken.stof())} verschillende opgaven die nooit geleerd "
      f"mogen worden.")
