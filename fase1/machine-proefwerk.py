"""Het bevroren proefwerk machine — de tiende familie (18 aug 2026, uit haar zwakteprofiel).

Een kleine registermachine: start, stappen, herhaal n keer, wat is x? Wat
zij leert te schrijven is het spoor — elke tussenwaarde — precies wat de
geheugen-steen (33%) en de diepe rijen (38%) van haar vragen.

    machine 1 … 12, 30 per diepte, 360 samen

Nummers vanaf 1.500.000; het slot houdt de leerstof erbuiten.

Draaien op de DL380 (moederkopie), één keer:
  venv/bin/python fase1/machine-proefwerk.py
"""
import sys
sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world

DIEPTES = range(1, 13)
PER_DIEPTE = 30
START = 1_500_000
ROOM = 1536 - 112

if exams.exists("machine"):
    sys.exit("proefwerk 'machine' bestaat al — een proefwerk wordt nooit "
             "overschreven; niets gedaan")

slot = exams.material()
gekozen = []
for diepte in DIEPTES:
    n = START
    per, geprobeerd, te_lang = [], 0, 0
    while len(per) < PER_DIEPTE:
        if n > START + 200_000:
            sys.exit(f"machine {diepte}: nummerruimte op — stop")
        t = world.make("machine", diepte, n)
        n += 1
        geprobeerd += 1
        if t is None:
            continue
        if not world.fits(t, ROOM):
            te_lang += 1
            continue
        if t.problem in slot or any(t.problem == g.problem for g in per):
            continue
        # Nakijken moet op de eigen uitwerking uitkomen — anders is het
        # geen eerlijke opgave maar een fout in de grammatica.
        if not t.check(t.working or t.solution):
            sys.exit(f"machine {diepte} nummer {n - 1}: uitwerking komt niet "
                     f"op de oplossing uit — stop")
        per.append(t)
    langste = max(len(t.problem) + len(t.to_learn()) for t in per)
    gekozen += per
    print(f"  machine diepte {diepte:>2}: {len(per)} opgaven uit {geprobeerd} "
          f"nummers ({te_lang} te lang), langste {langste} tekens")

aantal = exams.freeze(
    "machine",
    "De tiende familie (18 aug 2026, uit haar zwakteprofiel): een kleine "
    "registermachine (1-3 registers, 1-4 stappen, 1-4 rondes, vanaf 7 een "
    "als-stap); zij schrijft het spoor en het gevraagde register. Diepte 1 "
    "t/m 12, 30 per diepte, nummers vanaf 1.500.000. Vastgelegd vóór de knip "
    "na run 7.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
