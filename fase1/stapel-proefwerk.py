"""Het achtste bevroren proefwerk: stapel (15 aug 2026, op Cleys woord).

Waarom: op 15 aug 2026 is de wereld op twee plekken gegroeid — code
stapelt vanaf diepte 16 zijn blokken (filter in een lus, def over een
lijst, lus in lus, def die def aanroept; drie blokken vanaf 20), en de
puzzel kreeg de keer-plus-steen (`x → 2x + b`, 1 op 5 nummers vanaf
diepte 2). Geen enkel bestaand blad meet die stof: diepte3 stopt bij code
15 en heeft geen keer-plus-rijen. Zonder meetlat zie je bij run 6 niet of
ze het leert. Startstreep nu naar verwachting ~0%: ze heeft dit nooit
gezien.

    code     16, 18, 20, 22, 24     (twee blokken t/m 19, drie vanaf 20)
    puzzel   2, 4, 6, 8             (alléén keer-plus-rijen)

33 per vakje, 297 samen, alles past op venster 1024. Nummers vanaf
1.500.000: voorbij de leerlus (0–500.000) en voorbij de blokken van de
andere bladen (gesprek 500.000, ladder 800.000, diepte 900.000, diepte3
1.200.000).

Het code-hek staat op de DL380 nog op 15 (run 5); de wereld zelf kent de
diepte al. Het hek is een instelling van het run-tijdperk, geen grens van
de grammatica — hier tijdelijk opgerekt in het proces, world.py blijft
onaangeroerd. Op de rungrens zet rungrens.py het hek zelf (`--hek
code=24`).

Zoals elk proefwerk: de opgaven zelf worden bevroren, geen recept; het
mag er nooit meer uit; en na het vastleggen weigert de leerstof deze
teksten (het slot op inhoud). Een proefwerk plaatsen kan alléén op een
rungrens (zie rungrens.py): take() draait elk json-bestand dat hij ziet.

  venv/bin/python fase1/stapel-proefwerk.py
"""
import sys

sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world
from tasks import Picker, _mix

ROOM = 1024 - 112
PER_VAKJE = 33
START = 1_500_000
DIEPTES = {
    "code": (16, 18, 20, 22, 24),
    "puzzel": (2, 4, 6, 8),
}

# alleen in dit proces: de wereld kent de diepte, het hek is van run 5
world.MAX_DEPTH_PER["code"] = max(world.MAX_DEPTH_PER["code"], 24)


def is_keerplus(depth, n, task):
    """Draagt dit nummer de keer-plus-steen? Zelfde afleiding als make()."""
    seed = world._seed_of("puzzel", depth, n)
    k = Picker(_mix(seed ^ world.KEERPLUS_SEED))
    if depth < world.KEERPLUS_MIN or k.integer(1, 5) != 1:
        return False
    kp = world._row(depth, k, bases=("keer-plus",), extra=2)
    return kp[0] is not None and kp[0] == task.problem


slot = exams.material()
gekozen = []
for fam in ("code", "puzzel"):
    for diepte in DIEPTES[fam]:
        n = START
        per, geprobeerd, te_lang, geen_kp = [], 0, 0, 0
        while len(per) < PER_VAKJE:
            if n > START + 200_000:
                sys.exit(f"{fam} {diepte}: nummerruimte op — stop")
            t = world.make(fam, diepte, n)
            n += 1
            geprobeerd += 1
            if t is None:
                continue
            if fam == "puzzel" and not is_keerplus(diepte, n - 1, t):
                geen_kp += 1
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
              f"{geprobeerd} nummers ({te_lang} te lang, {geen_kp} geen "
              f"keer-plus), langste {langste} tekens")

aantal = exams.freeze(
    "stapel",
    "Uit de wereld van 15 aug 2026, de nieuwe stof: code 16, 18, 20, 22, 24 "
    "(gestapelde vormen: filter in een lus, def over een lijst, lus in lus, "
    "def die def aanroept; drie blokken vanaf 20) en puzzel 2, 4, 6, 8 met "
    "uitsluitend keer-plus-rijen (x → 2x + b). Alles past op venster 1024. "
    "Vastgelegd vóór run 6 als meetlat voor de wereldbouw van 15 aug.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
