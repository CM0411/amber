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

*(2 en 3 van de oorspronkelijke lijst zijn op 10 aug 's avonds overbodig
geworden: leerstofgrens en schrijfruimtes volgen sindsdien het venster
vanzelf — zie de startlijst onderaan.)*

1. Checkpoint van run 3 laden, `groei_venster(768)`, verder — géén verse start
2. Tempo meten, raming bijstellen, en de eerste 1000 stappen de ladder in de
   gaten houden: de nieuwe diepten komen als lege vakjes de nieuwsgierigheid in

## Herbevestigd op 10 aug, avond — de drievoudige controle voor run 4

1. **Op haar echte checkpoint** (stap 104.000): groei 512 → 768 bit voor bit
   gelijk, reeks van 700 tekens draait, en een checkpoint mét venster 768
   erin komt er gelijk weer uit. Niet alleen op het speelgoednet dus.
2. **De wereld hermeten mét de grammatica van 10 aug** (eindes, wisselende
   puzzellengtes): hekken blijven rekenen 26 (99% past), code 11 (100%),
   puzzel 6 (95% van bruikbaar past).
3. **Alle versteende getallen gevangen:** flessenhals, leerstofgrens én de
   schrijfruimte-plafonds volgen nu het venster (plafond = venster − marge
   per familie: rekenen −128, code −192, puzzel −72 — bij 512 exact de oude
   waarden). Antwoorden heeft een bestaand vangnet (inkorten, niet omvallen).

### Startlijst run 4 (na de Engels-migratie)
- checkpoint laden → `groei_venster(768)` → verder, geen verse start
- hekken: MEESTE_DIEPTE 26, per-familie code 11 / puzzel 6
- wrapper: stappental run 4; rapport-maker op nieuw doel en nieuwe hek-tekst
- venster-UI: grens {rekenen 26, code 11, puzzel 6}; kijker-diepten meegroeien
- eerste 1000 stappen: tempo aflezen en de eindtijd bijstellen

## 11 aug, avond — alles klaargezet; starten is nog twee commando's

De hele startlijst hierboven is uitgevoerd en gecontroleerd, plus de
Engelse omschakeling en de werelduitbreiding (som-van-vorige-twee,
×4–×6-rijen, proefwerkmaat-lussen en -def's). Hekken hermeten mét die
nieuwe vormen op 768: rekenen 26 → 99%, code 11 → 100%, puzzel 6 → 94%.

Wat er nu al staat:
- `fase1/leven/momentopname.pt` op de X399 **is** het run-4-startpunt:
  stap 170.000, venster 768, vorm in het checkpoint, geheugen 20.000 mee,
  stapelruimte 30.000 (beleid volgt de code, niet het checkpoint)
- run-3-eindstand veiliggesteld als `fase1/run3-eind.pt` op beide
  machines (md5 gelijk); DL380 heeft ook `fase1/run4-start.pt`
- wrapper staat bewust nog op `life.py 170000`: een herstart van de X399
  is dan een onschuldige no-op in plaats van een ongevraagde run-4-start
  ("zwijgen is nee" geldt ook voor systemd)
- `~/rapport/run4.json.klaar` ligt klaar naast de rapportmaker

**Startprocedure zodra Cley "start run 4" zegt:**
1. X399: in `~/nacht` het stappental `170000` → `320000`
   (170.000 gedaan + 150.000 nieuw; life.py telt absoluut)
2. DL380: `cp ~/rapport/run4.json.klaar ~/rapport/run.json`
3. X399: `sudo systemctl start amber-train`
4. Eerste 1000 stappen tempo aflezen en de eindtijd bevestigen
   (voorlopige raming: zie tempo-ijking hieronder)
