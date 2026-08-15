# Hekmeting — hoe diep mag de wereld open bij een groter venster?

15 aug 2026, DL380, `fase1/hek-meting.py 500` (uitvoer in `hek-meting.txt`).
Alleen CPU, 8 seconden. Regel: een diepte gaat open als ≥85% van de
bruikbare opgaven mét uitwerking in `venster − 112` past, en de kamer
niet leeg is (≥10% bruikbaar). Vensterkosten zelf: 1536 en 2048 kosten
niets extra (`venster-kosten.py`, dezelfde middag).

## Uitkomst per venster (85%-regel)

| venster | rekenen | code | puzzel |
|---|---|---|---|
| 1024 (nu) | 38 | (30) | 10 |
| 1536 | 60 | (30) | 10 |
| 2048 | 82 | (30) | 10 |

## Wat het betekent

- **Rekenen is de enige familie waar het venster de muur is.** Op 1024
  past diepte 38 voor 97%, 40 voor 78%, 42 voor 21%. Op 1536 past alles
  tot 60 (95%); op 2048 tot 82. Uitwerking op diepte 60: mediaan ~1000
  tekens — dat is de prijs bij pogingen (één treuzelaar bepaalt de duur)
- **Code wordt voorbij ~15 niet dieper.** Alles past (mediaan ~300
  tekens, ook op diepte 30), maar de grammatica plafonneert: `regels`
  max 6 regels / expressiediepte 4, `lijst` max 9 getallen, `def` max 15
  rondes; alleen de kale lus groeit mee met de diepte. Het hek 15 is dus
  geen venstergrens maar het einde van de wereld. Dieper voor code
  betekent **nieuwe bouwstenen in world.py**, geen venster
- **Puzzel: de muur is de uitlegbaarheid, niet de lengte.** Bruikbaar
  31% (d7), 26% (d8), 23% (d9), 21% (d10) — en dan **5–6% vanaf 11**.
  Diepte 10 past op 1024 voor 87% (13 aug: 80%; steekproefverschil), op
  1536 voor 100%. Diepte 11+ zijn lege kamers: elke partij dezelfde
  handvol opgaven. Dieper voor puzzel betekent een weefregel die vaker
  een uitleg oplevert, geen venster
- Dus voor de maat van run 6: het venster helpt alléén rekenen. Code en
  puzzel vragen wereldbouw — precies wat de startstreep van diepte3 al
  liet zien (code en puzzel tegen het plafond van de wereld)

## Wat dit niet meet

Of ze de diepste dieptes ook kan léren, en wat langere uitwerkingen aan
pogingtijd kosten op de Z490 — dat is de tempo-proef op de rungrens.

## Na de wereldbouw van 15 aug (17:10)

- **Code stapelt vanaf 16** (lus-filter, def-lijst, lus-lus, def-def; drie
  blokken vanaf 20). Alles past op 1024 (mediaan 190–270 tekens); de
  maten plafonneren rond 24. Het code-hek voor run 6 is dus een
  wereldgrens, **24**, niet de 30 die de pasmeting noemt
- **Puzzel kreeg de keer-plus-steen** (1 op 5 nummers vanaf diepte 2,
  eigen zaad). Bruikbaar op 7–10 nu 34/30/26/22%; diepte 11+ blijft een
  lege kamer (7%). Hek **10** bij 1024 (87%) en bij 1536 (100%)
- Rekenen ongewijzigd: 38 → 60 → 82
