"""Foutanalyse per vakje — niet hóéveel ze mist, maar wát ze mist.

Voor de zwakke vakjes van een rungrens: laat het eindbrein alle opgaven
van die vakjes maken en schrijf elke misser uit — opgave, wat zíj schreef,
wat het had moeten zijn. De patronen daarin zeggen of het aan de stof ligt
(één soort gaat stelselmatig mis), aan de manier (ze schat in plaats van
rekent) of aan toegang (past niet). Leest alleen; verandert niets aan haar.

  venv/bin/python fase1/foutanalyse.py <checkpoint> [proefwerk/]familie:graad ...
  bv.: fase1/foutanalyse.py fase1/leven-trainer/momentopname.pt \
       code:3 code:5 rekenen:3                 (grondslag, zoals altijd)
       fase1/foutanalyse.py fase1/leven/momentopname.pt \
       diepte2/rekenen:9 diepte2/code:6        (een ander proefwerk)
       fase1/foutanalyse.py fase1/leven/momentopname.pt ladder/*
                                               (alle vakjes van dat proefwerk)

Zonder proefwerknaam is het `grondslag` — zo blijft cijfers-bij-finish
werken zoals hij was. Uitgebreid op 15 aug 2026: de andere proefwerken
(diepte2, ladder, gemengd, gesprek) waren een blinde vlek — het cijfer was
zichtbaar, de missers niet.

Per proefwerk komt eerst een overzicht van álle vakjes (goed van totaal),
zodat je ziet waar het lek zit, en daarna de missers van de gevraagde
vakjes. De schrijfruimte is dezelfde als bij het proefwerk zelf
(`exams.take`): per familie de diepste graad van dat proefwerk — anders
meet je hier iets anders dan wat het cijfer zag.
"""
import sys

sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinism
determinism.lock(999)          # alleen antwoorden, geen leren — zaad vormvrij

import bridge
import exams
import learning
import snapshot

if len(sys.argv) < 3:
    sys.exit("gebruik: foutanalyse.py <checkpoint> [proefwerk/]familie:graad ...")
PAD = sys.argv[1]

# {proefwerknaam: [(familie, graad), ...] of None voor "alles"}
GEVRAAGD = {}
for arg in sys.argv[2:]:
    naam, _, vak = arg.rpartition("/")
    naam = naam or "grondslag"
    if vak == "*":
        GEVRAAGD[naam] = None
        continue
    fam, graad = vak.split(":")
    if GEVRAAGD.get(naam, []) is not None:
        GEVRAAGD.setdefault(naam, []).append((fam, int(graad)))

learner = learning.Learner(batch_size=32)
content = snapshot.read(PAD, device=learner.device)
learner.adopt_shape((content.get("extra") or {}).get("vorm"))
step = snapshot.restore(content, learner.core, learner.optimizer,
                        learner.device)
extra = content.get("extra") or {}
vorm = extra.get("vorm")
if vorm:
    learner.adopt_window(bridge.translate_spec(vorm).get("window") or 0)
learner.core.eval()
window = learner.core.window
print(f"checkpoint van stap {step:,}".replace(",", ".")
      + f" · venster {window}")

for naam, vakjes in GEVRAAGD.items():
    if not exams.exists(naam):
        print(f"\n=== proefwerk '{naam}' bestaat niet "
              f"(wel: {', '.join(exams.names())}) ===")
        continue
    exam = exams.load(naam)
    per_cell = {}
    for t in exam.as_tasks():
        per_cell.setdefault((t.family, t.grade), []).append(t)
    if vakjes is None:
        vakjes = sorted(per_cell)

    # Zelfde ruimte als het proefwerk: per familie de diepste graad.
    deepest = {}
    for fam, graad in per_cell:
        deepest[fam] = max(deepest.get(fam, 0), graad)

    # Eerst het hele blad, alle vakjes, één keer antwoorden per vakje.
    print(f"\n##### proefwerk {naam} — {exam.description}")
    uitkomst = {}
    for cel in sorted(per_cell):
        fam, graad = cel
        batch = per_cell[cel]
        answers = learner.answer(
            batch, at_most=learning.room_for(deepest[fam], fam, window))
        uitkomst[cel] = [(t, a) for t, a in zip(batch, answers)]
        goed = sum(1 for t, a in uitkomst[cel] if t.check(a))
        print(f"  {fam:>8} graad {graad:>2}: {goed:>3} van {len(batch):>3}"
              f"  ({goed / len(batch):.0%})")

    # Dan de missers van de gevraagde vakjes.
    for fam, graad in vakjes:
        paren = uitkomst.get((fam, graad))
        if paren is None:
            print(f"\n=== {naam}/{fam} graad {graad}: niet in dit proefwerk ===")
            continue
        missers = [(t, a) for t, a in paren if not t.check(a)]
        print(f"\n=== {naam}/{fam} graad {graad}: {len(paren) - len(missers)} "
              f"van {len(paren)} goed — {len(missers)} missers ===")
        for t, a in missers:
            print(f"\n--- opgave {t.number} ---")
            print(t.problem)
            print(f"    zij : {a!r}")
            print(f"    goed: {t.working or t.solution!r}")
