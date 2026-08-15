"""Tempo-ijking venster 768 op de X399 — leest alleen, schrijft niets.

Laadt het run-4-startcheckpoint zoals life.py dat doet, draait een
handvol echte leerstappen in het geheugen en meet ms/stap plus één
proefwerk. Het proces eindigt zonder ook maar één bestand aan te raken;
run 4 zelf begint pas op Cleys woord, vanaf het onaangeroerde
momentopname-bestand.
"""
import sys, time
sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinism
determinism.lock(20260808)
import torch
import bridge, exams, learning, snapshot

inhoud = snapshot.read("/home/arch/amber-werk/fase1/leven/momentopname.pt",
                       device="cuda")
import os
L = learning.Learner(batch_size=64,
                     checkpointing=os.environ.get("AMBER_CHECKPOINTING") == "1")
L.adopt_shape((inhoud.get("extra") or {}).get("vorm"))
stap = snapshot.restore(inhoud, L.core, L.optimizer, L.device)
extra = inhoud.get("extra") or {}
L.adopt_window(bridge.translate_spec(extra["vorm"]).get("window"))
L.restore(extra)
L.steps = stap
print(f"geladen: stap {stap}, venster {L.core.window}, "
      f"geheugen {len(L.memory)}, partij {L.batch_size}, bf16 {L.bf16}, "
      f"lagen {len(L.core.blocks)}, checkpointing {L.core.checkpointing}")

# opwarmen (compilatie, allocator) — telt niet mee
for s in range(stap + 1, stap + 6):
    L.work(s)
torch.cuda.synchronize()

N = 60
t0 = time.perf_counter()
for s in range(stap + 6, stap + 6 + N):
    L.work(s)
torch.cuda.synchronize()
per_stap = (time.perf_counter() - t0) / N * 1000
piek = torch.cuda.max_memory_allocated() / 1024**2

t0 = time.perf_counter()
exams.take(L, at_most=150)
proefwerk_s = time.perf_counter() - t0

NIEUW = 150_000
werk_u = NIEUW * per_stap / 1000 / 3600
pw_u = (NIEUW / 500) * proefwerk_s / 3600
print(f"tempo: {per_stap:.0f} ms/stap | VRAM-piek {piek:.0f} MB")
print(f"proefwerk (150 opgaven): {proefwerk_s:.0f} s")
print(f"raming 150.000 stappen: {werk_u:.1f} u werk + {pw_u:.1f} u "
      f"proefwerken = {werk_u + pw_u:.1f} uur")
