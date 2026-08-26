"""
Tests the honest "?" and the play hour (25 Aug 2026, Claude's wishes 1 and 3).

Enforced here:
* check(): a lone "?" as the last piece is right for family onbekend, None
  (neither) for any other task; numbers and words still mark as before;
* score_of(): a wrong answer costs half a point, a "?" nothing, never below 0;
* the world's family onbekend: deterministic, solution "?", twelve depths,
  no collision with the exams;
* the play hour: in a play step no self-test, no curiosity update, no gate
  opens, and the step still learns; outside it the old behaviour.

Run:  CUDA_VISIBLE_DEVICES= python3 kern/test-onbekend.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import determinism                 # before torch
determinism.lock(1)
import torch

import exams
import learning
import network
import tasks
import world
from learning import Learner, score_of, telling, speelt, SPEL_PERIODE, SPEL_DUUR

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        print(f"  FOUT: {name} {detail}")


def T(family, solution, problem="x", number=5000):
    return tasks.Task(family=family, grade=1, number=number, problem=problem, solution=solution, working=None)


# --- check() -------------------------------------------------------------
t = T("rekenen", "7")
check("getal goed", t.check("3 + 4 = 7") is True)
check("getal fout", t.check("8") is False)
check("? bij een som is None", t.check("?") is None)
check("? na een uitwerking is None", t.check("3 + 4 = ? ; ?") is None)
check("een ? midden in de tekst telt niet als ?", t.check("wat ? 7") is True)
u = T("onbekend", "?")
check("onbekend: ? is goed", u.check("?") is True)
check("onbekend: gok is fout", u.check("12") is False)
check("onbekend: woord is fout", u.check("kat") is False)
w = T("taal", "kat")
check("woord goed", w.check("de kat zit ; kat") is True)
check("woord ? is None", w.check("?") is None)

# --- score_of() ----------------------------------------------------------
check("score alles goed", score_of([True] * 4) == 1.0)
check("score 10 goed 10 fout = 0,25", abs(score_of([True] * 10 + [False] * 10) - 0.25) < 1e-9)
check("score 10 goed 10 ? = 0,5", abs(score_of([True] * 10 + [None] * 10) - 0.5) < 1e-9)
check("score alles fout = 0, niet negatief", score_of([False] * 5) == 0.0)
check("score leeg = 0", score_of([]) == 0.0)
check("telling", telling([True, False, None, None]) == (1, 1, 2))

# --- de familie onbekend -------------------------------------------------
check("onbekend in de wereld, achteraan", world.FAMILIES[-1] == "onbekend")
check("hek van onbekend", world.max_depth("onbekend") == 16)   # 26 aug 2026: 12 -> 16 (run 7.5)
gezien = set()
for depth in range(1, world.max_depth("onbekend") + 1):
    for n in range(0, 30):
        a = world.make("onbekend", depth, n)
        b = world.make("onbekend", depth, n)
        check("deterministisch", a == b, f"{depth}/{n}")
        check("oplossing is ?", a.solution == "?", f"{depth}/{n}: {a.solution!r}")
        check("uitwerking is ?", a.working == "?")
        check("opgave niet leeg", len(a.problem) > 8)
        check("opgave past", len(a.problem) < 200)
        gezien.add(a.problem)
check("genoeg verschillende opgaven", len(gezien) > 120, str(len(gezien)))
# De kale generator mag toevallig een tekst maken die ook op het bevroren
# blad staat — de tekstruimte is klein op lage dieptes. Wat telt is het
# slot: de leerlus geeft exclude=exams.material() mee (learning.py), dus
# leerstof bevat nooit een proefwerktekst. Dat slot toetsen we hier, op
# elke diepte. (26 aug 2026: de oude botsing-check gold alleen doordat de
# knip-volgorde het blad pas ná de toets bevroor.)
mat = exams.material()
for depth in range(1, world.max_depth("onbekend") + 1):
    leer = world.learning_tasks("onbekend", depth, 8, start=0, room=400,
                                exclude=mat)
    check("slot houdt proefwerk buiten de leerstof",
          not any(t.problem in mat for t in leer), f"diepte {depth}")
leer = world.learning_tasks("onbekend", 5, 8, start=0, room=400, exclude=set())
check("leerstof onbekend", len(leer) == 8 and all(t.solution == "?" for t in leer))

# --- het speeluur --------------------------------------------------------
check("speeluur: begin van de periode", speelt(0) and speelt(SPEL_DUUR - 1))
check("speeluur: daarna niet", not speelt(SPEL_DUUR) and not speelt(SPEL_PERIODE - 1))
check("speeluur: volgende dag weer", speelt(SPEL_PERIODE) and speelt(2 * SPEL_PERIODE + 3))
aandeel = sum(1 for s in range(SPEL_PERIODE) if speelt(s)) / SPEL_PERIODE
check("ongeveer een uur per dag", 0.03 < aandeel < 0.06, f"{aandeel:.3f}")

torch.manual_seed(3)
core = network.Core(layers=2, width=32, heads=2, window=256)
L = Learner(core=core, device="cpu", batch_size=4, bf16=False, probe_every=1)
# a play step: probe_every=1 would test every step, but not in the play hour
voor_hek = dict(L.deepest_per); voor_score = dict(L.curiosity.score)
r = L.work(4)                                          # 4 < SPEL_DUUR: play
check("speelstap gemarkeerd", r["spel"] is True)
check("speelstap: geen cijfer", r["score"] is None and r["goed"] is None)
check("speelstap: leert wel", r["loss"] is not None)
check("speelstap: hek onveranderd", L.deepest_per == voor_hek)
check("speelstap: nieuwsgierigheid onveranderd", dict(L.curiosity.score) == voor_score)
r2 = L.work(SPEL_DUUR + 8)                             # outside the hour: the old road
check("gewone stap: geen spel", r2["spel"] is False)
check("gewone stap: wel een cijfer", r2["score"] is not None and r2["goed"] is not None)
check("gewone stap: telling klopt", r2["goed"] + r2["fout"] + r2["weetniet"] == 4)

print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(1 if failed else 0)
