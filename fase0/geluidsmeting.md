# Geluidsmeting — fase 0

Beide kaarten tegelijk belast, 180 s per stap. Het oordeel is van Cley, die naast de server zit.

| stap | stand | verbruik samen | temp | klok | oordeel |
|---|---|---:|---:|---:|---|
| 1 | 544 MHz vastgezet  (het laagste dat de kaart kan) | 159 W | 68 °C | 544 MHz | zacht hoorbaar |
| 2 | ~~700 MHz~~ ONGELDIG — klok bleef op 544 MHz staan, dit is stap 1 opnieuw | 162 W | 72 °C | 544 MHz | (niet meegeteld) |
| 2 | **696 MHz vastgezet** (herstart na de correctie) | niet vastgelegd | — | 696 MHz | **het maximaal aanvaardbare** |

Verder gemeten is er niet: stap 3 en hoger zijn overgeslagen omdat het antwoord er al was.

## Uitkomst

**696 MHz is het plafond, en tevens de standaardstand.** Geldt voor als er niemand
in de kamer is en voor de nacht. Vol vermogen mag, maar alleen als Cley het zelf
aanzet wanneer hij het nodig heeft — het is nooit de stand waar de machine
vanzelf in terechtkomt.

Ter vergelijking: 696 MHz is 52% van de maximale 1328 MHz. Bij 544 MHz trokken
beide kaarten samen 159 W; bij 250 W per kaart is dat 500 W. De stille stand
kost dus rekenkracht, maar levert wel echt werk — dit is geen fluisterstand
waarin niets gebeurt.

**Niet vastgelegd:** het verbruik bij 696 MHz. Het script is bij die stap
afgesloten zonder ingetypt oordeel, dus de meetregel is nooit weggeschreven.
Alsnog te meten wanneer de opstart-unit getest wordt.
