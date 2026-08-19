"""Het bevroren proefwerk antwoord — de twaalfde familie (19 aug 2026, Cley: terug kunnen praten).

Een korte stand van haarzelf (cijfers, wereld, keuzes) en een vraag; het
antwoord is een zin uit een vaste kleine woordenschat, nagekeken als tekst.

    antwoord 1 … 12, 30 per diepte, 360 samen

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

if exams.exists("antwoord"):
    sys.exit("proefwerk 'zeggen' bestaat al — een proefwerk wordt nooit "
             "overschreven; niets gedaan")

slot = exams.material()
gekozen = []
for diepte in DIEPTES:
    n = START
    per, geprobeerd, te_lang = [], 0, 0
    while len(per) < PER_DIEPTE:
        if n > START + 200_000:
            sys.exit(f"antwoord {diepte}: nummerruimte op — stop")
        t = world.make("antwoord", diepte, n)
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
            sys.exit(f"antwoord {diepte} nummer {n - 1}: uitwerking komt niet "
                     f"op de oplossing uit — stop")
        per.append(t)
    langste = max(len(t.problem) + len(t.to_learn()) for t in per)
    gekozen += per
    print(f"  antwoord diepte {diepte:>2}: {len(per)} opgaven uit {geprobeerd} "
          f"nummers ({te_lang} te lang), langste {langste} tekens")

aantal = exams.freeze(
    "antwoord",
    "De twaalfde familie (19 aug 2026): zij leert wat Cleys antwoord op haar "
    "vraag betekent — ja, nee, later, eerst X, en geen antwoord = ik wacht "
    "(zwijgen is nee). Graad 10-12: twee beurten, het laatste geldt. "
    "Nagekeken als tekst. Diepte 1 t/m 12, 30 per diepte, "
    "nummers vanaf 1.500.000. Vastgelegd vóór de knip na run 7.1.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
