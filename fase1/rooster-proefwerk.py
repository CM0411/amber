"""Het bevroren proefwerk rooster — de derde puzzelsteen (18 aug 2026, op Cleys woord).

Waarom: het rooster (Latijns vierkant / som-rooster / keer-rooster met één
of meer geketende onbekenden) is nieuwe stof in puzzel; geen bestaand blad
meet die stof. Dit blad neemt alleen rooster-opgaven.

    puzzel 1 … 12 (alleen rooster), 30 per diepte, 360 samen

Nummers vanaf 1.500.000; het slot houdt de leerstof erbuiten.

Draaien op de DL380 (moederkopie), één keer:
  venv/bin/python fase1/rooster-proefwerk.py
"""
import sys
sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world

DIEPTES = range(1, 13)
PER_DIEPTE = 30
START = 1_500_000
ROOM = 1536 - 112

if exams.exists("rooster"):
    sys.exit("proefwerk 'rooster' bestaat al — een proefwerk wordt nooit "
             "overschreven; niets gedaan")

slot = exams.material()
gekozen = []
for diepte in DIEPTES:
    n = START
    per, geprobeerd, te_lang = [], 0, 0
    while len(per) < PER_DIEPTE:
        if n > START + 200_000:
            sys.exit(f"rooster {diepte}: nummerruimte op — stop")
        t = world.make("puzzel", diepte, n)
        n += 1
        geprobeerd += 1
        if t is None or not t.problem.startswith("rooster"):
            continue
        if not world.fits(t, ROOM):
            te_lang += 1
            continue
        if t.problem in slot or any(t.problem == g.problem for g in per):
            continue
        # Nakijken moet op de eigen uitwerking uitkomen — anders is het
        # geen eerlijke opgave maar een fout in de grammatica.
        if not t.check(t.working or t.solution):
            sys.exit(f"rooster {diepte} nummer {n - 1}: uitwerking komt niet "
                     f"op de oplossing uit — stop")
        per.append(t)
    langste = max(len(t.problem) + len(t.to_learn()) for t in per)
    gekozen += per
    print(f"  rooster diepte {diepte:>2}: {len(per)} opgaven uit {geprobeerd} "
          f"nummers ({te_lang} te lang), langste {langste} tekens")

aantal = exams.freeze(
    "rooster",
    "De derde puzzelsteen (18 aug 2026): een rooster met een regel over "
    "rijen en kolommen — Latijns vierkant (1 tot n één keer), som-rooster "
    "(elke rij en kolom telt op tot S), keer-rooster (rij keer kolom); vanaf "
    "diepte 7 geketende onbekenden (* eerst via de kolom, dan ? via de rij). "
    "Diepte 1 t/m 12, 30 per diepte, nummers vanaf 1.500.000. Vastgelegd vóór "
    "de knip na run 7.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
