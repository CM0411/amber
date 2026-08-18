"""Het bevroren proefwerk taal — de negende familie (18 aug 2026, Cleys wens: een stuk taal).

Korte Nederlandse zinnetjes uit een vast klein woordenboek met een vraag
(wie / wat doet / waar / welke kleur / wat is), vanaf 9 verwijzingen (hij,
daar), vanaf 11 een zin maken uit geschudde woorden; nagekeken als tekst.

    taal 1 … 12, 30 per diepte, 360 samen

Nummers vanaf 1.500.000; het slot houdt de leerstof erbuiten.

Draaien op de DL380 (moederkopie), één keer:
  venv/bin/python fase1/taal-proefwerk.py
"""
import sys
sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world

DIEPTES = range(1, 13)
PER_DIEPTE = 30
START = 1_500_000
ROOM = 1536 - 112

if exams.exists("taal"):
    sys.exit("proefwerk 'taal' bestaat al — een proefwerk wordt nooit "
             "overschreven; niets gedaan")

slot = exams.material()
gekozen = []
for diepte in DIEPTES:
    n = START
    per, geprobeerd, te_lang = [], 0, 0
    while len(per) < PER_DIEPTE:
        if n > START + 200_000:
            sys.exit(f"taal {diepte}: nummerruimte op — stop")
        t = world.make("taal", diepte, n)
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
            sys.exit(f"taal {diepte} nummer {n - 1}: uitwerking komt niet "
                     f"op de oplossing uit — stop")
        per.append(t)
    langste = max(len(t.problem) + len(t.to_learn()) for t in per)
    gekozen += per
    print(f"  taal diepte {diepte:>2}: {len(per)} opgaven uit {geprobeerd} "
          f"nummers ({te_lang} te lang), langste {langste} tekens")

aantal = exams.freeze(
    "taal",
    "De negende familie (18 aug 2026): begrijpen (zinnetjes uit een vast "
    "woordenboek van dieren, dingen, kleuren en werkwoorden, met een vraag), "
    "verwijzen (hij, daar; vanaf 9) en maken (de zin uit geschudde woorden; "
    "vanaf 11). Nagekeken als tekst. Diepte 1 t/m 12, 30 per diepte, nummers "
    "vanaf 1.500.000. Vastgelegd vóór de knip na run 7.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
