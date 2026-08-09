# Wat kost de stilte?

Gemeten op 696 MHz, de werkstand. Vergeleken met de
waarden bij de standaardklok van 8 aug 2026.

## Doorvoer, één kaart, fp32

| matrix | 696 MHz | vol vermogen | verhouding |
|---:|---:|---:|---:|
| 1024 | 3.25 TF | 5.27 TF | 62% |
| 2048 | 4.04 TF | 6.31 TF | 64% |
| 4096 | 4.35 TF | 8.02 TF | 54% |
| 8192 | 4.57 TF | 8.64 TF | 53% |

**Gemiddeld 58% van vol vermogen.**

## Beide kaarten samen onder belasting

- verbruik samen: **182 W**
- hoogste temperatuur: 62 °C

Ter vergelijking: bij vol vermogen trekken twee kaarten samen ongeveer 500 W.
De stille stand kost dus **36% van het vermogen en levert 58% van het werk** —
per watt is 696 MHz ongeveer 45% zuiniger dan vol vermogen (50 tegen 35
GFLOPS/W). De stilte kost minder dan de vermogensdaling doet vermoeden.

## De prijs van determinisme

fp32 bij matrix 4096: 4.33 TFLOPS zonder, 4.37 met — **-0.8% kosten**.

Alleen op matmul gemeten is dat een halve waarheid: cudnn komt daar niet aan te
pas, en juist dáár zitten de kosten normaal — `cudnn.benchmark=False` schakelt
het uitzoeken van het snelste algoritme uit. Daarom apart nagemeten:

| bewerking | zonder | met | kosten |
|---|---:|---:|---:|
| matmul fp32, 4096 | 4,33 TF | 4,37 TF | geen meetbaar verschil |
| conv voor+achterwaarts | 6,09 ms | 6,32 ms | **3,9%** |

**Determinisme kost op deze hardware hooguit een paar procent.** De roadmap
noemde het als een reële prijs; dat valt mee. Het is geen argument om het
ergens uit te laten.
