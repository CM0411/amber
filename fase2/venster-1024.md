# Venster 1024 — de hekmeting voor run 5 (12 aug 2026)

Gemeten op de DL380 met de wereld van 12 aug (incl. proefwerkmaat-def's
tot 15 rondes), ruimte = 1024 − 112 = 912, 300 opgaven per diepte,
maatstaf: ≥85% van de bruikbare opgaven past mét uitwerking.

| familie | 26 | 29 | 32 | 35 | 38 | | 11 | 12 | 13 | 14 | 15 | | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rekenen | 100% | 100% | 100% | 99% | 97% | | | | | | | | | | |
| code | | | | | | | 100% | 100% | 100% | 100% | 99% | | | | |
| puzzel | | | | | | | | | | | | | 100% | 76% | 30% |

**Hekken voor run 5 (venster 1024): rekenen 38 · code 15 · puzzel 6.**

- Code 15 = de volledige proefwerkmaat: de def met vijftien rondes
  (grondslag graad 5, `range(1, 16)`) past dan eindelijk — de laatste
  proefwerkstof die nu nog buiten bereik is.
- Puzzel blijft op 6: diepte 7 haalt 76% (onder de maat) en de echte
  rem is daar niet het venster maar de verklaring van diep vervlochten
  rijen (4–16% bruikbaar). Een hek verder vraagt een nieuwe
  verklaarmethode, geen groter venster.
- De def-vorm maakt sinds 12 aug tot 15 rondes; tijdens run 4 (768)
  filtert `fits()` alles boven ~10 rondes gewoon weg — de wereld mag
  vooruit gemaakt zijn, het venster bepaalt per tijdperk wat ze ziet.

Startlijst run 5 (bij het run-4-einde): checkpoint → `grow_window(1024)`,
MAX_DEPTH 38 / code 15 (puzzel blijft 6), run.json en vensterlabels,
tempo-ijking, en de nameting per vakje van run 4 als nulpunt.
