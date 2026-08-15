# De CPU-kloof gemeten — 15 aug 2026

Vraag: de GPU-benutting van run 5 zakt tussen stappen naar 40–50% en de
trainer zit op één kern op 98%. Zit daar 10–20% tempo?

Meting: `fase1/kloof-meting.py` op de DL380 (P100, één kaart), 40 stappen
vanaf de momentopname van stap 351.000, geheugen en nieuwsgierigheid
teruggezet zoals life.py dat doet, elk stuk apart geklokt met de kaart
leeggelopen aan beide kanten.

momentopname stap 351.000 · venster 1024 · geheugen 30.000 · cuda

40 stappen, 10 met poging, 290.2 s totaal, 7254 ms/stap
  met poging  : 13.90 s  (n=10)
  zonder      : 5.04 s  (n=30)

waar de tijd zit (over alle stappen):
  leren (kaart: voor/achter/optimizer)    198.73 s  68.5%  (80 keer, 2484.1 ms per keer)
  antwoorden (kaart, autoregressief)       86.41 s  29.8%  (10 keer, 8641.4 ms per keer)
  geheugen: onthouden                       3.39 s   1.2%  (3200 keer, 1.1 ms per keer)
  partij bouwen (tekens→tensor)             0.92 s   0.3%  (80 keer, 11.5 ms per keer)
  taken maken (wereld)                      0.41 s   0.1%  (40 keer, 10.3 ms per keer)
  geheugen: herhalen kiezen                 0.10 s   0.0%  (80 keer, 1.3 ms per keer)
  geheugen: herinnering→taak                0.07 s   0.0%  (2560 keer, 0.0 ms per keer)
  nakijken (check)                          0.02 s   0.0%  (640 keer, 0.0 ms per keer)
  proefwerkslot ophalen                     0.01 s   0.0%  (40 keer, 0.2 ms per keer)
  nieuwsgierigheid: kiezen                  0.00 s   0.0%  (40 keer, 0.1 ms per keer)
  nieuwsgierigheid: bijwerken               0.00 s   0.0%  (10 keer, 0.0 ms per keer)
  rest (Python-lijm in work/learn)          0.09 s   0.0%

kaart samen 285.1 s = 98%; de rest (5.0 s = 2%) is CPU — dat is de kloof.

## Wat het zegt

- **Er is geen CPU-kloof van betekenis.** Taken maken, nakijken, geheugen,
  partij bouwen: samen 5 s op 293 s = 2%. Op de Z490 is de kaart ~3× zo
  snel en de CPU eerder sneller, dus daar hooguit ~5%. Geen 10–20% te
  halen zonder de kaart-kant aan te raken
- **De dips van 40–50% komen uit het antwoorden zelf:** letter voor
  letter, per letter zo'n honderd kleine kernels door acht lagen. Op een
  trage kaart (P100) merk je dat niet — de kaart is de flessenhals. Op de
  3070 Ti is de kaart per letter sneller klaar dan Python de volgende
  letter kan afvuren, en dan wacht ze. Dat is een launch-probleem, geen
  Python-probleem
- Het middel daarvoor is CUDA-graphs of torch.compile op de
  antwoordlus. compile is op 14 aug afgewezen (geen bit-gelijkheid);
  CUDA-graphs is een echt project (vaste vormen, eigen cache) en de
  winst is hooguit ~1 s op een poging van 3,9 s → ~10% op het geheel.
  Niet nu
- Bijvangst: elke `work()` doet twéé optimizerstappen (64 nieuwe taken →
  40 + 24, elk aangevuld met herhaling tot 64). Zo staat het sinds de
  nulmeting (partij 32 → 16 + 16); geen fout, wel goed om te weten bij
  het lezen van "ms/stap"
