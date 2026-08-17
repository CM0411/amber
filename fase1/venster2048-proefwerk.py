"""Het twaalfde bevroren proefwerk: venster2048 (17 aug 2026, op Cleys woord).

Waarom: het venster gaat ooit van 1536 naar 2048 (ontwerp 17 aug 2026,
no-go voor nu). Dat opent rekenen voorbij 60 en code voorbij 30 — en die
stof moet op de dag van de groei meteen meetbaar zijn. Dit blad ligt
daarom klaar met een venster-eis: exams.take slaat het over zolang haar
venster kleiner is dan 2048, dus het kan zonder gevaar mee op elke grens.

    rekenen 62, 66, 70, 74, 78 en code 32, 34, 36, 38, 40 — 30 per vakje, 300 samen

Nummers vanaf 1.500.000: voorbij de leerlus (0–500.000) en voorbij de
blokken van de andere bladen; het slot houdt de leerstof erbuiten. Alles
past op venster 1536.

Draaien op de DL380 (moederkopie), één keer:
  venv/bin/python fase1/venster2048-proefwerk.py
"""
import sys
sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world

VAKJES = [("rekenen", d) for d in (62, 66, 70, 74, 78)] + [("code", d) for d in (32, 34, 36, 38, 40)]
PER_DIEPTE = 30
START = 1_500_000
VENSTER = 2048
ROOM = VENSTER - 112

if exams.exists("venster2048"):
    sys.exit("proefwerk 'venster2048' bestaat al — een proefwerk wordt nooit "
             "overschreven; niets gedaan")

slot = exams.material()
import learning
world.MAX_DEPTH = max(world.MAX_DEPTH, 80)                     # het blad reikt voorbij het huidige hek
world.MAX_DEPTH_PER["code"] = max(world.MAX_DEPTH_PER.get("code", 0), 40)
gekozen = []
for fam, diepte in VAKJES:
    n = START
    per, geprobeerd, te_lang = [], 0, 0
    while len(per) < PER_DIEPTE:
        if n > START + 200_000:
            sys.exit(f"{fam} {diepte}: nummerruimte op — stop")
        t = world.make(fam, diepte, n)
        n += 1
        geprobeerd += 1
        if t is None:
            continue
        if not world.fits(t, ROOM) or len(t.to_learn()) > learning.room_for(diepte, fam, VENSTER):
            te_lang += 1
            continue
        if t.problem in slot or any(t.problem == g.problem for g in per):
            continue
        # Nakijken moet op de eigen uitwerking uitkomen — anders is het
        # geen eerlijke opgave maar een fout in de grammatica.
        if not t.check(t.working or t.solution):
            sys.exit(f"{fam} {diepte} nummer {n - 1}: uitwerking komt niet "
                     f"op de oplossing uit — stop")
        per.append(t)
    langste = max(len(t.problem) + len(t.to_learn()) for t in per)
    gekozen += per
    print(f"  {fam} diepte {diepte:>2}: {len(per)} opgaven uit {geprobeerd} "
          f"nummers ({te_lang} te lang), langste {langste} tekens")

aantal = exams.freeze(
    "venster2048",
    "Klaargelegd voor de groei naar venster 2048 (17 aug 2026): rekenen 62, "
    "66, 70, 74, 78 en code 32, 34, 36, 38, 40 — de stof die 1536 niet "
    "kan dragen. 30 per vakje, nummers vanaf 1.500.000, past met uitwerking "
    "op 2048. Wordt overgeslagen zolang haar venster kleiner is dan 2048.",
    gekozen,
    window=VENSTER,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
