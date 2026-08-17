"""Het elfde bevroren proefwerk: regel (17 aug 2026, op Cleys woord).

Waarom: met run 6.7 krijgt de puzzel zijn tweede soort — de "welke
regel"-puzzel: een verborgen regel uit stenen (+c, ×a, kwadraat), getoond
door paren, gevraagd op een nieuwe invoer; boven diepte 10 (waar de rijen
een lege kamer zijn) is elke puzzel van deze soort. Geen bestaand blad
meet die stof; dit blad neemt alleen regelpuzzels.

    puzzel 1 … 20 (alleen regelpuzzels; het puzzel-hek van run 6.7), 20 per diepte, 400 samen

Nummers vanaf 1.500.000: voorbij de leerlus (0–500.000) en voorbij de
blokken van de andere bladen; het slot houdt de leerstof erbuiten. Alles
past op venster 1536.

Draaien op de DL380 (moederkopie), één keer:
  venv/bin/python fase1/regel-proefwerk.py
"""
import sys
sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world

DIEPTES = range(1, 21)
PER_DIEPTE = 20
START = 1_500_000
ROOM = 1536 - 112

if exams.exists("regel"):
    sys.exit("proefwerk 'regel' bestaat al — een proefwerk wordt nooit "
             "overschreven; niets gedaan")

slot = exams.material()
world.MAX_DEPTH_PER["puzzel"] = max(world.MAX_DEPTH_PER.get("puzzel", 0), 20)   # het blad reikt tot 20
gekozen = []
for diepte in DIEPTES:
    n = START
    per, geprobeerd, te_lang = [], 0, 0
    while len(per) < PER_DIEPTE:
        if n > START + 200_000:
            sys.exit(f"regel {diepte}: nummerruimte op — stop")
        t = world.make("puzzel", diepte, n)
        n += 1
        geprobeerd += 1
        if t is None or not t.problem.startswith("regel: "):
            continue                      # alleen de regelpuzzels
        if not world.fits(t, ROOM):
            te_lang += 1
            continue
        if t.problem in slot or any(t.problem == g.problem for g in per):
            continue
        # Nakijken moet op de eigen uitwerking uitkomen — anders is het
        # geen eerlijke opgave maar een fout in de grammatica.
        if not t.check(t.working or t.solution):
            sys.exit(f"regel {diepte} nummer {n - 1}: uitwerking komt niet "
                     f"op de oplossing uit — stop")
        per.append(t)
    langste = max(len(t.problem) + len(t.to_learn()) for t in per)
    gekozen += per
    print(f"  regel diepte {diepte:>2}: {len(per)} opgaven uit {geprobeerd} "
          f"nummers ({te_lang} te lang), langste {langste} tekens")

aantal = exams.freeze(
    "regel",
    "De tweede puzzelsoort (17 aug 2026): welke regel? Een verborgen regel "
    "uit stenen (+c, ×a, kwadraat), getoond door twee tot vier paren, "
    "gevraagd op een nieuwe invoer; twee paren = lineair, vanaf diepte 7 "
    "drie paren en ook kwadraten. Puzzel diepte 1 t/m 20, alleen "
    "regelpuzzels, 20 per diepte, nummers vanaf 1.500.000. Alles past op "
    "venster 1536. Vastgelegd vóór run 6.7.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
