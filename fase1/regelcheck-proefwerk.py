"""Het bevroren proefwerk regelcheck — de brug-steen in puzzel (18 aug 2026, Cleys idee).

Waarom: de trap naar inductie. In de regelpuzzel moet zij een regel
raden; hier verifieert zij regels met wat zij al kan rekenen: klopt
f(5) = 16 bij f(x) = 3 * x + 1 (1/0), en vanaf diepte 4: welke van drie
regels past bij alle paren (het regelnummer). Dit blad neemt alleen
regelcheck-opgaven.

    puzzel 1 … 12 (alleen regelcheck), 30 per diepte, 360 samen

Nummers vanaf 1.500.000: voorbij de leerlus (0–500.000) en voorbij de
blokken van de andere bladen; het slot houdt de leerstof erbuiten. Alles
past op venster 1536.

Draaien op de DL380 (moederkopie), één keer:
  venv/bin/python fase1/regelcheck-proefwerk.py
"""
import sys
sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world

DIEPTES = range(1, 13)
PER_DIEPTE = 30
START = 1_500_000
ROOM = 1536 - 112

if exams.exists("regelcheck"):
    sys.exit("proefwerk 'regelcheck' bestaat al — een proefwerk wordt nooit "
             "overschreven; niets gedaan")

slot = exams.material()
gekozen = []
for diepte in DIEPTES:
    n = START
    per, geprobeerd, te_lang = [], 0, 0
    while len(per) < PER_DIEPTE:
        if n > START + 200_000:
            sys.exit(f"regelcheck {diepte}: nummerruimte op — stop")
        t = world.make("puzzel", diepte, n)
        n += 1
        geprobeerd += 1
        if t is None or not t.problem.startswith(("controleer: ", "paren: ")):
            continue
        if not world.fits(t, ROOM):
            te_lang += 1
            continue
        if t.problem in slot or any(t.problem == g.problem for g in per):
            continue
        # Nakijken moet op de eigen uitwerking uitkomen — anders is het
        # geen eerlijke opgave maar een fout in de grammatica.
        if not t.check(t.working or t.solution):
            sys.exit(f"regelcheck {diepte} nummer {n - 1}: uitwerking komt niet "
                     f"op de oplossing uit — stop")
        per.append(t)
    langste = max(len(t.problem) + len(t.to_learn()) for t in per)
    gekozen += per
    print(f"  regelcheck diepte {diepte:>2}: {len(per)} opgaven uit {geprobeerd} "
          f"nummers ({te_lang} te lang), langste {langste} tekens")

aantal = exams.freeze(
    "regelcheck",
    "De brug-steen in puzzel (18 aug 2026, Cleys idee): regels verifiëren "
    "in plaats van raden — diepte 1 t/m 3 klopt f(x) = y? (1/0), vanaf 4 "
    "welke van drie regels past bij alle paren, vanaf 8 ook kwadraatregels. "
    "Diepte 1 t/m 12, 30 per diepte, nummers vanaf 1.500.000. Vastgelegd "
    "vóór run 7 als meetlat voor de trap verifiëren → kiezen → raden.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
