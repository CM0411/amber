"""Het zevende bevroren proefwerk: diepte3 (15 aug 2026, op Cleys woord).

Waarom: diepte2 en ladder zaten op stap 351.000 van run 5 op hun plafond
— niet omdat ze vastliep, maar omdat die bladen bevroren zijn van vóór de
rijlengte-regel van 13 aug 2026. Hun diepe puzzels tonen zes getallen,
en daaruit is het patroon meestal niet te halen: van diepte2 puzzel 6/9
was 8 van 33 en 2 van 33 überhaupt uitlegbaar, en zij haalde 7 en 1.
Ladder puzzel 5/6: 4 en 3 van 20 uitlegbaar, zij haalde 4 en 3. Een
meter die vol is meet niets meer.

Dit blad komt uit de wereld zoals ze nú is: de wereld gooit zelf elke
puzzel weg die niet uit de getoonde getallen op te lossen is (`make`
geeft dan None), dus hier zit alleen oplosbaar spul in — dat probleem
komt niet terug. En de diepte is ruim genomen, zodat er jaren ruimte is:

    rekenen  3, 6, 9, 12, 18, 24, 30   (hek 38)
    code     3, 6, 9, 12, 15            (15 is het maximum van de wereld)
    puzzel   3, 6, 9                    (9 is het maximum van de wereld)

33 per vakje, 495 samen, alles past op venster 1024. Nummers vanaf
1.200.000: ver voorbij waar de leerlus trekt (0–500.000) en voorbij de
blokken van gesprek (500.000), ladder (800.000) en diepte (900.000).

Zoals elk proefwerk: de opgaven zelf worden bevroren, geen recept; het
mag er nooit meer uit; en na het vastleggen weigert de leerstof deze
teksten (het slot op inhoud). Wél de wereld zoals ze is — dus mét de
gespreksjas, de keersom-splits en de lange lussen waar die voorkomen.
Een proefwerk plaatsen kan alléén op een rungrens (zie rungrens.py):
take() draait elk json-bestand dat hij ziet.

  venv/bin/python fase1/diepte3-proefwerk.py
"""
import sys

sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world

ROOM = 1024 - 112
PER_VAKJE = 33
START = 1_200_000
DIEPTES = {
    "rekenen": (3, 6, 9, 12, 18, 24, 30),
    "code": (3, 6, 9, 12, 15),
    "puzzel": (3, 6, 9),
}

for fam, dieptes in DIEPTES.items():
    if max(dieptes) > world.max_depth(fam):
        sys.exit(f"{fam} {max(dieptes)} ligt boven het maximum van de "
                 f"wereld ({world.max_depth(fam)}) — stop")

slot = exams.material()
gekozen = []
for fam in ("code", "puzzel", "rekenen"):        # zelfde volgorde als de rest
    for diepte in DIEPTES[fam]:
        n = START
        per, geprobeerd, te_lang = [], 0, 0
        while len(per) < PER_VAKJE:
            if n > START + 200_000:
                sys.exit(f"{fam} {diepte}: nummerruimte op — stop")
            t = world.make(fam, diepte, n)
            n += 1
            geprobeerd += 1
            if t is None:
                continue
            if not world.fits(t, ROOM):
                te_lang += 1
                continue
            if t.problem in slot or any(t.problem == g.problem for g in per):
                continue
            # Nakijken moet op de eigen uitwerking uitkomen — anders is
            # het geen eerlijke opgave maar een fout in de grammatica.
            if not t.check(t.working or t.solution):
                sys.exit(f"{fam} {diepte} nummer {n - 1}: uitwerking komt "
                         f"niet op de oplossing uit — stop")
            per.append(t)
        langste = max(len(t.problem) + len(t.to_learn()) for t in per)
        gekozen += per
        print(f"  {fam:>8} diepte {diepte:>2}: {len(per)} opgaven uit "
              f"{geprobeerd} nummers ({te_lang} te lang), langste "
              f"{langste} tekens")

aantal = exams.freeze(
    "diepte3",
    "Uit de wereld van 15 aug 2026, over de volle diepte: rekenen 3, 6, 9, "
    "12, 18, 24, 30; code 3, 6, 9, 12, 15; puzzel 3, 6, 9. Alleen "
    "oplosbare rijen (de wereld gooit de rest zelf weg) en alles past op "
    "venster 1024. Vervangt diepte2 en ladder als dieptemeter: die zaten "
    "op hun plafond doordat hun diepe puzzels van vóór de rijlengte-regel "
    "van 13 aug 2026 stammen en zes getallen tonen waar het patroon niet "
    "uit te halen is.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
