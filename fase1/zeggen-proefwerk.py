"""Het bevroren proefwerk zeggen — de achtste familie (18 aug 2026, Cleys wens: zij vertelt zelf in letters wat ze wil).

Een korte stand van haarzelf (cijfers, wereld, keuzes) en een vraag; het
antwoord is een zin uit een vaste kleine woordenschat, nagekeken als tekst.

    zeggen 1 … 12, 30 per diepte, 360 samen

Nummers vanaf 1.500.000; het slot houdt de leerstof erbuiten.

Draaien op de DL380 (moederkopie), één keer:
  venv/bin/python fase1/zeggen-proefwerk.py
"""
import sys
sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world

DIEPTES = range(1, 13)
PER_DIEPTE = 30
START = 1_500_000
ROOM = 1536 - 112

if exams.exists("zeggen"):
    sys.exit("proefwerk 'zeggen' bestaat al — een proefwerk wordt nooit "
             "overschreven; niets gedaan")

slot = exams.material()
gekozen = []
for diepte in DIEPTES:
    n = START
    per, geprobeerd, te_lang = [], 0, 0
    while len(per) < PER_DIEPTE:
        if n > START + 200_000:
            sys.exit(f"zeggen {diepte}: nummerruimte op — stop")
        t = world.make("zeggen", diepte, n)
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
            sys.exit(f"zeggen {diepte} nummer {n - 1}: uitwerking komt niet "
                     f"op de oplossing uit — stop")
        per.append(t)
    langste = max(len(t.problem) + len(t.to_learn()) for t in per)
    gekozen += per
    print(f"  zeggen diepte {diepte:>2}: {len(per)} opgaven uit {geprobeerd} "
          f"nummers ({te_lang} te lang), langste {langste} tekens")

aantal = exams.freeze(
    "zeggen",
    "De achtste familie (18 aug 2026): haar eigen zin uit een vaste kleine "
    "woordenschat — oordeel (gaat goed / gaat / is moeilijk), wens (ik wil "
    "meer X oefenen, ik wil dieper in X, X blijft moeilijk), vanaf 11 twee "
    "zinnen met 'en'. Nagekeken als tekst. Diepte 1 t/m 12, 30 per diepte, "
    "nummers vanaf 1.500.000. Vastgelegd vóór de knip na run 7.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
