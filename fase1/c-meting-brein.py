"""De C-meting op het échte brein — wat kost een blok puzzels aan rekenen en code?

De nulmeting van 8 aug 2026 stond op een leeg netwerk: zonder bescherming
verdween 90%, met 37,5% herhaling bleef 71% over. Dit is dezelfde meting op
wie ze nu is (momentopname van run 5), met haar eigen geheugen van 30.000
herinneringen erbij. Open sinds 11 aug ("de C-meting opnieuw, nu ze echt
iets kan"); gedraaid 15 aug op de stille P100's van de DL380.

Opzet — leer A, leer B, meet wat A inlevert:
  A = wat ze al kan: rekenen en code, gemeten op grondslag + diepte3
  B = een blok van alléén puzzels (diepte 1–9 door elkaar), STAPPEN lang
  behouden = score-na / score-vóór, per familie, gemiddeld over de vakjes

Twee instellingen, zelfde rekenwerk per stap: elke stap is precies één
optimizerstap van 64 reeksen. Met herhaling 37,5% zijn dat 40 nieuwe + 24
oude, zonder herhaling 64 nieuwe — herhaling gaat ten koste van nieuw en
komt er niet bovenop (de regel van 8 aug). Blokwerk lokt vergeten uit; zo
hoort ze niet te leven, maar zo zie je het probleem op ware grootte.

Leest de momentopname, schrijft geen checkpoint; alleen een verslagregel.

  venv/bin/python fase1/c-meting-brein.py <checkpoint> --herhaling 0.375 \
      --stappen 1000 --zaad 1 [--uit verslag.txt]
"""
import argparse, sys, time
sys.path.insert(0, "/home/arch/amber-werk/kern")

p = argparse.ArgumentParser()
p.add_argument("checkpoint")
p.add_argument("--herhaling", type=float, default=0.375)
p.add_argument("--stappen", type=int, default=1000)
p.add_argument("--zaad", type=int, default=1)
p.add_argument("--uit", default=None)
a = p.parse_args()

import determinism
determinism.lock(20260815 + a.zaad)
import torch
import bridge, exams, learning, snapshot, world
import tasks as tasks_module
from learning import Learner

L = Learner(batch_size=64, replay_share=a.herhaling)
inhoud = snapshot.read(a.checkpoint, device=L.device)
L.adopt_shape((inhoud.get("extra") or {}).get("vorm"))
stap0 = snapshot.restore(inhoud, L.core, L.optimizer, L.device)
extra = inhoud.get("extra") or {}
L.adopt_window(bridge.translate_spec(extra["vorm"]).get("window"))
L.restore(extra)
L.steps = stap0
W = L.core.window
print(f"stap {stap0} · venster {W} · geheugen {len(L.memory)} · herhaling "
      f"{L.replay_share:.1%} → {L.new_per_batch} nieuw per partij · zaad {a.zaad}",
      flush=True)

BLADEN = ("grondslag", "diepte3")


def meet():
    """Score per (blad, familie, graad) — antwoorden alleen, zoals exams.take."""
    uit = {}
    for naam in BLADEN:
        ex = exams.load(naam)
        cellen = {}
        for t in ex.as_tasks():
            cellen.setdefault((t.family, t.grade), []).append(t)
        diepste = {}
        for fam, g in cellen:
            diepste[fam] = max(diepste.get(fam, 0), g)
        for (fam, g), batch in sorted(cellen.items()):
            antw = L.answer(batch, at_most=learning.room_for(diepste[fam], fam, W))
            uit[(naam, fam, g)] = sum(t.check(x) for t, x in zip(batch, antw)) / len(batch)
    return uit


def per_familie(scores):
    som, n = {}, {}
    for (_, fam, _), v in scores.items():
        som[fam] = som.get(fam, 0) + v
        n[fam] = n.get(fam, 0) + 1
    return {f: som[f] / n[f] for f in som}


t0 = time.perf_counter()
voor = meet()
pf_voor = per_familie(voor)
print("vóór :  " + "  ".join(f"{f} {v:.0%}" for f, v in sorted(pf_voor.items()))
      + f"   ({time.perf_counter() - t0:.0f} s)", flush=True)

# --- het blok puzzels ------------------------------------------------------
slot = exams.material()
t0 = time.perf_counter()
for k in range(a.stappen):
    stap = stap0 + 1 + k
    determinism.begin_step(stap)
    picker = tasks_module.Picker(determinism.seed_for_step(stap))
    diepte = picker.integer(1, world.max_depth("puzzel"))
    chunk = world.learning_tasks("puzzel", diepte, L.new_per_batch,
                                 start=picker.integer(0, 500_000),
                                 room=W - 112, exclude=slot)
    L.learn(chunk)                       # precies één optimizerstap van 64
    if (k + 1) % 100 == 0:
        per = (time.perf_counter() - t0) / (k + 1)
        print(f"  {k + 1}/{a.stappen} puzzelstappen, {per * 1000:.0f} ms/stap, "
              f"nog {(a.stappen - k - 1) * per / 60:.0f} min", flush=True)

na = meet()
pf_na = per_familie(na)
print("na   :  " + "  ".join(f"{f} {v:.0%}" for f, v in sorted(pf_na.items())))
behoud = {f: (pf_na[f] / pf_voor[f] if pf_voor[f] else None)
          for f in ("rekenen", "code")}
print("behouden:  " + "  ".join(f"{f} {v:.0%}" for f, v in behoud.items() if v is not None))
print("per vakje (vóór → na, alleen wat verschuift ≥ 5 punten):")
for k in sorted(voor):
    if abs(na[k] - voor[k]) >= 0.05:
        print(f"  {k[0]:>9} {k[1]:>8} {k[2]:>2}: {voor[k]:>4.0%} → {na[k]:>4.0%}")

if a.uit:
    with open(a.uit, "a") as f:
        f.write(f"herhaling {a.herhaling:.3f} zaad {a.zaad} stappen {a.stappen} | "
                + "vóór " + " ".join(f"{k}={v:.2f}" for k, v in sorted(pf_voor.items()))
                + " | na " + " ".join(f"{k}={v:.2f}" for k, v in sorted(pf_na.items()))
                + " | behouden " + " ".join(f"{k}={v:.2f}" for k, v in behoud.items() if v)
                + "\n")
