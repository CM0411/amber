"""Het bevroren proefwerk deling — de deel-steen in rekenen (18 aug 2026, op Cleys woord).

Waarom: de puzzel-audit vond dat delen nergens in haar wereld bestond,
terwijl regelpuzzels en delingen er stil om vroegen. Rekenen krijgt
kale delingen met exacte uitkomst en tafel-uitwerking (1 op 6 nummers,
diepte 3–12, alleen waar geen andere splitsing trok). Dit blad neemt
alleen delingen.

    rekenen 3 … 12 (alleen delingen), 30 per diepte, 300 samen

Nummers vanaf 1.500.000: voorbij de leerlus (0–500.000) en voorbij de
blokken van de andere bladen; het slot houdt de leerstof erbuiten. Alles
past op venster 1536.

Draaien op de DL380 (moederkopie), één keer:
  venv/bin/python fase1/deling-proefwerk.py
"""
import re
import sys
sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world

DIEPTES = range(3, 13)
PER_DIEPTE = 30
START = 1_500_000
ROOM = 1536 - 112

if exams.exists("deling"):
    sys.exit("proefwerk 'deling' bestaat al — een proefwerk wordt nooit "
             "overschreven; niets gedaan")

slot = exams.material()
gekozen = []
for diepte in DIEPTES:
    n = START
    per, geprobeerd, te_lang = [], 0, 0
    while len(per) < PER_DIEPTE:
        if n > START + 200_000:
            sys.exit(f"deling {diepte}: nummerruimte op — stop")
        t = world.make("rekenen", diepte, n)
        n += 1
        geprobeerd += 1
        if t is None or not re.fullmatch(r"\d+ : \d+", t.problem):
            continue
        if not world.fits(t, ROOM):
            te_lang += 1
            continue
        if t.problem in slot or any(t.problem == g.problem for g in per):
            continue
        # Nakijken moet op de eigen uitwerking uitkomen — anders is het
        # geen eerlijke opgave maar een fout in de grammatica.
        if not t.check(t.working or t.solution):
            sys.exit(f"deling {diepte} nummer {n - 1}: uitwerking komt niet "
                     f"op de oplossing uit — stop")
        per.append(t)
    langste = max(len(t.problem) + len(t.to_learn()) for t in per)
    gekozen += per
    print(f"  deling diepte {diepte:>2}: {len(per)} opgaven uit {geprobeerd} "
          f"nummers ({te_lang} te lang), langste {langste} tekens")

aantal = exams.freeze(
    "deling",
    "De deel-steen in rekenen (18 aug 2026): kale delingen met exacte "
    "uitkomst, deler 2 t/m 12, uitgewerkt via de tafel (7 * 12 = 84 ; "
    "84 : 7 = 12). Diepte 3 t/m 12, 30 per diepte, nummers vanaf "
    "1.500.000. Vastgelegd vóór run 7 als meetlat voor delen — de "
    "bewerking die tot nu toe nergens in haar wereld bestond.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
