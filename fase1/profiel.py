"""Profielronde (TE-DOEN 3 / pakket B, 18 aug 2026): waar zit de stap-tijd
en het VRAM op de run-7-vorm — gemeten op de DL380 (P100, bf16 geëmuleerd)
met de gegroeide opname, zonder de afronding te raken (alleen meten).

  venv/bin/python fase1/profiel.py [pad-naar-opname]

Meet per onderdeel van één `work()`-stap (rekenen 60, partij 64, 37,5%
herhaling): leerstof maken (wereld), antwoorden (probe, elke 4e stap),
geheugen-herinneren + herhaalselectie, de leerstap (voorwaarts, achterwaarts,
optimizer) met en zonder checkpointing, en een proefwerkportie; plus het
VRAM na elk deel. Getallen zijn ter vergelijking (P100 ≠ 3070 Ti); de
verhoudingen zijn wat telt.
"""
import sys, time, os
sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinism; determinism.lock(4242)
import torch, learning, network, world, exams, snapshot
MB = 1024 ** 2
pad = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/amber-werk/fase1/leven/momentopname.pt")

def sync(): torch.cuda.synchronize()
def klok(f, n=1):
    sync(); t0 = time.time()
    for _ in range(n): r = f()
    sync(); return (time.time() - t0) / n, r

import bridge
L = learning.Learner(batch_size=64, checkpointing=True)
content = snapshot.read(pad, device=L.device)
extra = content.get("extra") or {}
if extra.get("vorm"):
    L.adopt_shape(bridge.translate_spec(extra["vorm"]))
stap = snapshot.restore(content, L.core, L.optimizer, L.device)
L.steps = stap
if "geheugen" in extra:
    L.restore(extra, step=stap)
core = L.core
print(f"vorm: {len(core.blocks)} lagen, venster {core.window}, {core.parameter_count()/1e6:.1f} M, geheugen {len(L.memory)} herinneringen, checkpointing {core.checkpointing}")
torch.cuda.reset_peak_memory_stats()
determinism.begin_step(1)
t, stof = klok(lambda: world.learning_tasks("rekenen", 60, 64, start=100, room=core.window - 112, exclude=exams.material()))
print(f"leerstof maken (rekenen 60, 64 taken): {t*1000:.0f} ms")
t, given = klok(lambda: L.answer(stof, at_most=learning.room_for(60, "rekenen", core.window)))
print(f"antwoorden (probe, 64 taken): {t*1000:.0f} ms · VRAM piek {torch.cuda.max_memory_allocated()/MB:.0f} MB")
torch.cuda.reset_peak_memory_stats()
t, _ = klok(lambda: [L.memory.remember(x, x.solution, None) for x in stof])
print(f"herinneren (64): {t*1000:.0f} ms")
import tasks as tm
t, _ = klok(lambda: L.memory.replay(24, tm.Picker(determinism.seed_for_step(L.steps))))
print(f"herhaalselectie (24 uit {len(L.memory)}): {t*1000:.0f} ms")
for ck in (True, False):
    core.checkpointing = ck
    torch.cuda.reset_peak_memory_stats()
    determinism.begin_step(2)
    t, _ = klok(lambda: L.learn(stof, remember=False), n=2)
    print(f"leerstap (2 partijen 64) checkpointing {'aan' if ck else 'uit'}: {t*1000:.0f} ms · VRAM piek {torch.cuda.max_memory_allocated()/MB:.0f} MB")
core.checkpointing = True
torch.cuda.reset_peak_memory_stats()
t, sc = klok(lambda: exams.take(L, "grondslag", at_most=150))
print(f"proefwerk grondslag (150 opgaven): {t:.1f} s · VRAM piek {torch.cuda.max_memory_allocated()/MB:.0f} MB")
if hasattr(torch, "profiler"):
    determinism.begin_step(3)
    with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CUDA]) as prof:
        L.learn(stof, remember=False)
    print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=12))
