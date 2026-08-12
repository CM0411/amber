"""Nameting per vakje — wat kan ze écht, gemeten op de bevroren grondslag.

Voor een rungrens: één commando, vijf minuten, en je ziet per familie en
graad de score plus hoe haar herhaalgeheugen over de vakjes ligt. Leest
alleen; verandert niets aan haar.

  venv/bin/python fase1/nameting.py [checkpoint]     (anders fase1/nu.pt)
"""
import sys

sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinism
determinism.lock(999)          # alleen antwoorden, geen leren — zaad vormvrij

import bridge
import exams
import learning
import snapshot

PAD = sys.argv[1] if len(sys.argv) > 1 else "/home/arch/amber-werk/fase1/nu.pt"

learner = learning.Learner(batch_size=32)
content = snapshot.read(PAD, device=learner.device)
step = snapshot.restore(content, learner.core, learner.optimizer,
                        learner.device)
extra = content.get("extra") or {}
vorm = extra.get("vorm")
if vorm:
    learner.adopt_window(bridge.translate_spec(vorm).get("window") or 0)
if extra.get("geheugen"):
    learner.restore(extra)
learner.core.eval()
print(f"checkpoint van stap {step:,}".replace(",", ".")
      + f" · venster {learner.core.window}\n")

# --- het geheugen, per vakje -------------------------------------------------
tally = {}
for stored in learner.memory._content:
    cell = (stored["familie"], stored["graad"])
    tally[cell] = tally.get(cell, 0) + 1
print(f"geheugen: {len(learner.memory):,} herinneringen".replace(",", "."))
for fam in ("rekenen", "code", "puzzel"):
    grades = sorted(g for f, g in tally if f == fam)
    if grades:
        print(f"  {fam:<8} " + "  ".join(f"{g}:{tally[(fam, g)]:>5}"
                                         for g in grades))

# --- grondslag per vakje -----------------------------------------------------
exam = exams.load("grondslag")
per_cell = {}
for t in exam.as_tasks():
    per_cell.setdefault((t.family, t.grade), []).append(t)

print("\ngrondslag per vakje (score, aantal opgaven):")
for (fam, grade) in sorted(per_cell):
    batch = per_cell[(fam, grade)]
    answers = learner.answer(
        batch, at_most=learning.room_for(grade, fam, learner.core.window))
    right = sum(1 for t, a in zip(batch, answers) if t.check(a))
    print(f"  {fam:<8} graad {grade}:  {100 * right // len(batch):>3}%   "
          f"({len(batch)})")
