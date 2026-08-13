"""Het vierde bevroren proefwerk: gesprek (13 aug 2026, op Cleys woord).

Run 5 gaat de gespreksjas leren — rekenvragen zoals Cley ze stelt
("Wat is 13 keer 8?", "Reken uit: …"). De drie bestaande proefwerken
meten alleen kale sommen, dus zonder dit blad is de jas onmeetbaar en
leert ze iets waar nooit een cijfer op komt.

Zoals elk proefwerk: de opgaven zelf worden bevroren, geen recept; het
mag er nooit meer uit; en na het vastleggen weigert de leerstof deze
teksten (het slot op inhoud). Dertig opgaven per diepte 2–8, uit een
vers stuk van de nummerruimte (vanaf 500.000), passend op venster 1024.
"""
import sys

sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world

ROOM = 1024 - 112
PER_DIEPTE = 30
START = 500_000

slot = exams.material()
gekozen = []
for diepte in range(2, 9):
    n = START
    per, spreek = [], 0
    while len(per) < PER_DIEPTE:
        if n > START + 200_000:
            sys.exit(f"diepte {diepte}: nummerruimte op — stop")
        t = world.make("rekenen", diepte, n)
        n += 1
        if t is None or not world.fits(t, ROOM):
            continue
        jas = t.problem.endswith("?") or t.problem.startswith("Reken uit:")
        if not jas or t.problem in slot:
            continue
        per.append(t)
        if "keer" in t.problem or "plus" in t.problem or "min" in t.problem:
            spreek += 1
    gekozen += per
    print(f"diepte {diepte}: {len(per)} opgaven, {spreek} in spreektaal")

aantal = exams.freeze(
    "gesprek",
    "De gespreksjas: rekenvragen zoals Cley ze stelt — 'Wat is …?', "
    "'Hoeveel is …?', 'Reken uit: …', in cijfers en in spreektaal. "
    "Dertig per diepte 2 t/m 8, vastgelegd 13 aug 2026.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
