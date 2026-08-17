"""Het bevroren proefwerk geheugen2 — de geheugen-steen (17 aug 2026, op Cleys woord).

Waarom: de geheugen-steen (17 aug 2026): een lopende toestand — rekenende
updates (k = k + 3, p = p * 2) en verwijzingen (p = k, en kettingen). Het
bestaande geheugen-blad meet alleen de eerste vorm; dit blad neemt
uitsluitend steen-opgaven (de zaadsplitsing STEEN_SEED, 1 op 3 vanaf
diepte 4), zodat je apart ziet of zij een toestand kan bijhouden.

    geheugen 4 … 24 (alleen steen-opgaven), 20 per diepte, 420 samen

Nummers vanaf 1.500.000: voorbij de leerlus (0–500.000) en voorbij de
blokken van de andere bladen; het slot houdt de leerstof erbuiten. Alles
past op venster 1536.

Draaien op de DL380 (moederkopie), één keer:
  venv/bin/python fase1/geheugen2-proefwerk.py
"""
import sys
sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world

DIEPTES = range(4, 25)
PER_DIEPTE = 20
START = 1_500_000
ROOM = 1536 - 112

if exams.exists("geheugen2"):
    sys.exit("proefwerk 'geheugen2' bestaat al — een proefwerk wordt nooit "
             "overschreven; niets gedaan")

slot = exams.material()
import tasks
world.MAX_DEPTH_PER["geheugen"] = max(world.MAX_DEPTH_PER.get("geheugen", 0), 24)


def is_steen(diepte, nummer):
    seed = world._seed_of("geheugen", diepte, nummer)
    return diepte >= world.STEEN_MIN and tasks.Picker(tasks._mix(seed ^ world.STEEN_SEED)).integer(1, 3) == 1
gekozen = []
for diepte in DIEPTES:
    n = START
    per, geprobeerd, te_lang = [], 0, 0
    while len(per) < PER_DIEPTE:
        if n > START + 200_000:
            sys.exit(f"geheugen2 {diepte}: nummerruimte op — stop")
        if not is_steen(diepte, n):
            n += 1
            continue
        t = world.make("geheugen", diepte, n)
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
            sys.exit(f"geheugen2 {diepte} nummer {n - 1}: uitwerking komt niet "
                     f"op de oplossing uit — stop")
        per.append(t)
    langste = max(len(t.problem) + len(t.to_learn()) for t in per)
    gekozen += per
    print(f"  geheugen2 diepte {diepte:>2}: {len(per)} opgaven uit {geprobeerd} "
          f"nummers ({te_lang} te lang), langste {langste} tekens")

aantal = exams.freeze(
    "geheugen2",
    "De geheugen-steen (17 aug 2026): een lopende toestand — rekenende "
    "updates (k = k + 3, p = p * 2, begrensd) en verwijzingen (p = k, "
    "kettingen vanaf 9), tussen de gewone afleiders; vragen als bij "
    "geheugen. Diepte 4 t/m 24, alleen steen-opgaven, 20 per diepte, "
    "nummers vanaf 1.500.000. Alles past op venster 1536.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
