"""Het bevroren proefwerk volgorde — de zesde familie (18 aug 2026, op Cleys woord).

Waarom: met de volgende knip komt de zesde taakfamilie in haar wereld —
volgorde: stappen van een plan in een geschudde nummering, regels die de
orde vastleggen, en een vraag naar een plaats. Relationeel redeneren, geen
rekenen. Geen bestaand blad meet die stof; zonder meetlat vanaf stap 0 zie
je niet of ze het leert, en of het oude eronder lijdt.

    volgorde 1 … 12     (het hek), 30 per diepte, 360 samen

Nummers vanaf 1.500.000: voorbij de leerlus (0–500.000) en voorbij de
blokken van de andere bladen; het slot houdt de leerstof erbuiten. Alles
past op venster 1536.

Draaien op de DL380 (moederkopie), één keer:
  venv/bin/python fase1/volgorde-proefwerk.py
"""
import sys
sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world

DIEPTES = range(1, 13)
PER_DIEPTE = 30
START = 1_500_000
ROOM = 1536 - 112

if exams.exists("volgorde"):
    sys.exit("proefwerk 'volgorde' bestaat al — een proefwerk wordt nooit "
             "overschreven; niets gedaan")

slot = exams.material()
gekozen = []
for diepte in DIEPTES:
    n = START
    per, geprobeerd, te_lang = [], 0, 0
    while len(per) < PER_DIEPTE:
        if n > START + 200_000:
            sys.exit(f"volgorde {diepte}: nummerruimte op — stop")
        t = world.make("volgorde", diepte, n)
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
            sys.exit(f"volgorde {diepte} nummer {n - 1}: uitwerking komt niet "
                     f"op de oplossing uit — stop")
        per.append(t)
    langste = max(len(t.problem) + len(t.to_learn()) for t in per)
    gekozen += per
    print(f"  volgorde diepte {diepte:>2}: {len(per)} opgaven uit {geprobeerd} "
          f"nummers ({te_lang} te lang), langste {langste} tekens")

aantal = exams.freeze(
    "volgorde",
    "De zesde taakfamilie (18 aug 2026): stappen in geschudde nummering, "
    "regels (na / voor / direct na / tussen) die precies één volgorde "
    "vastleggen, vraag naar een plaats of de plaats van een stap. Diepte 1 "
    "t/m 12, 30 per diepte, nummers vanaf 1.500.000. Alles past op venster "
    "1536. Vastgelegd vóór de knip als meetlat voor de volgorde-familie én "
    "als C-toets naast de andere bladen.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
