"""Het bevroren proefwerk vergelijking — de vergelijkingssteen in rekenen (18 aug 2026, op Cleys woord).

Waarom: rekenen krijgt een steen die terugrekent — een onbekende x uit
een vergelijking, door de bewerkingen ongedaan te maken (1 op 4 nummers,
diepte 3–20, alleen waar geen andere splitsing trok). Geen bestaand blad
meet die stof; dit blad neemt alleen vergelijkingen.

    rekenen 3 … 20 (alleen vergelijkingen), 20 per diepte, 360 samen

Nummers vanaf 1.500.000: voorbij de leerlus (0–500.000) en voorbij de
blokken van de andere bladen; het slot houdt de leerstof erbuiten. Alles
past op venster 1536.

Draaien op de DL380 (moederkopie), één keer:
  venv/bin/python fase1/vergelijking-proefwerk.py
"""
import sys
sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world

DIEPTES = range(3, 21)
PER_DIEPTE = 20
START = 1_500_000
ROOM = 1536 - 112

if exams.exists("vergelijking"):
    sys.exit("proefwerk 'vergelijking' bestaat al — een proefwerk wordt nooit "
             "overschreven; niets gedaan")

slot = exams.material()
gekozen = []
for diepte in DIEPTES:
    n = START
    per, geprobeerd, te_lang = [], 0, 0
    while len(per) < PER_DIEPTE:
        if n > START + 200_000:
            sys.exit(f"vergelijking {diepte}: nummerruimte op — stop")
        t = world.make("rekenen", diepte, n)
        n += 1
        geprobeerd += 1
        if t is None or not ("wat is x?" in t.problem):
            continue
        if not world.fits(t, ROOM):
            te_lang += 1
            continue
        if t.problem in slot or any(t.problem == g.problem for g in per):
            continue
        # Nakijken moet op de eigen uitwerking uitkomen — anders is het
        # geen eerlijke opgave maar een fout in de grammatica.
        if not t.check(t.working or t.solution):
            sys.exit(f"vergelijking {diepte} nummer {n - 1}: uitwerking komt niet "
                     f"op de oplossing uit — stop")
        per.append(t)
    langste = max(len(t.problem) + len(t.to_learn()) for t in per)
    gekozen += per
    print(f"  vergelijking diepte {diepte:>2}: {len(per)} opgaven uit {geprobeerd} "
          f"nummers ({te_lang} te lang), langste {langste} tekens")

aantal = exams.freeze(
    "vergelijking",
    "De vergelijkingssteen in rekenen (18 aug 2026): x vinden door de "
    "bewerkingen ongedaan te maken — één stap (3–5), twee stappen (6–8), x "
    "aan twee kanten (9–12), haakjes en drie stappen (13–20); antwoord "
    "altijd geheel. Rekenen diepte 3 t/m 20, alleen vergelijkingen, 20 per "
    "diepte, nummers vanaf 1.500.000. Alles past op venster 1536.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
