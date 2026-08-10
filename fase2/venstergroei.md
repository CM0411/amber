# Venstergroei — de eerste steen van fase 2

*10 aug 2026, gebouwd tijdens run 3 (niet op de lopende run uitgerold).*

## Wat er is gebouwd

`netwerk.Kern.groei_venster(nieuw)` — het venster groter maken zonder dat er
iets aan haar verandert. Dit verzilvert het ontwerp van dag één: posities
gaan via draaiing (RoPE) en die heeft geen parameters, dus het venster is in
de hele kern maar op één plek bekend, als grens in `vooruit`. Groeien is die
grens verleggen. Krimpen weigert.

Bewezen in `toets-venstergroei.py` (8 toetsen, alle groen op 10 aug 2026):

- **Zelfde invoer, zelfde uitvoer, bit voor bit** na groei 64 → 96
- Venstergroei voegt **nul parameters** toe
- Het gebied voorbij het oude venster is echt open; voorbij het nieuwe
  venster weigert hij zoals eerst
- **Een checkpoint van vóór de groei verhuist mee**: schrijven met venster
  64, laden, groeien naar 96, en de uitvoer is bit voor bit die van het
  origineel. Het run-3-checkpoint kan run 4 dus in met een groter venster,
  zonder één parameter te verliezen

## Wat 768 opent — gemeten

Tekstruimte bij venster 768: 656 (zelfde marge van 112 als nu bij 512).
300 opgaven per vakje; "past" is opgave + volledige uitwerking binnen 656.

| familie | hek nu (512) | hek bij 768 | gemeten |
|---|---:|---:|---|
| rekenen | 17 | **26** | past 99–100% tot en met 26 |
| code | 8 | **11** | 100% t/m 11; 64% op 12; 3% op 15 |
| puzzel | 5 | **6** | álle verklaarbare opgaven op 6 passen (was 2%) |

Zelfde maatstaf als altijd: het hek staat waar ≥85% van de bruikbare opgaven
past. Puzzel 7 blijft dicht (10% past), en puzzelverklaring zelf blijft
~35% van de nummers — dat is de grammatica, niet het venster, en het is
hetzelfde percentage als op diepte 5 binnen het huidige hek.

De schrijfruimtes (`ruimte_voor` in leren.py) moeten bij run 4 meegroeien:
rekenen p95 op diepte 26 is 487 tekens (nu afgekapt op 384), code p95 op 11
is 401 (nu 320), puzzel diepte 6 vraagt 525 (nu 336).

## De prijs, eerlijk

- Aandacht is kwadratisch in de lengte: 768² / 512² = **2,25× rekenwerk in
  de aandachtslaag** voor volle vensters. De stukjes-achterwaartse-stap in
  leren.py deelt de partij vanzelf kleiner (budget / lengte²), dus het
  geheugen blijft passen op de 8 GB van de X399 — het kost tempo, geen VRAM.
- Werkelijk tempo bij 768 op de X399: **meten bij de start van run 4**, niet
  schatten. Pas dan de stappenraming van de run aan.

## Wat er bij de start van run 4 moet gebeuren

1. Checkpoint van run 3 laden, `groei_venster(768)`, verder — géén verse start
2. `wereld.MEESTE_TEKENS` 400 → 656, hekken naar 26 / 11 / 6
3. `ruimte_voor` per familie mee (zie boven), en de venstergrens in het
   antwoorden (512 in leren.py) naar 768
4. Tempo meten, raming bijstellen, en de eerste 1000 stappen de ladder in de
   gaten houden: de nieuwe diepten komen als lege vakjes de nieuwsgierigheid in
