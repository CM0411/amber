"""Wat kost een groter venster? — meet 1024 tegen 1536 (en 2048) op één kaart.

Laadt de momentopname zoals life.py, draait echte leerstappen (met
pogingen, herhaling, alles) op het huidige venster, groeit dan het venster
en meet opnieuw. Leest alleen; schrijft niets. De absolute tijden gelden
voor de kaart waarop dit draait (P100 hier); de verhouding is wat telt.
Let op: de P100 rekent in fp32, de 3070 Ti in bf16 — de VRAM-piek hier is
dus ruim aan de hoge kant voor de Z490.

  venv/bin/python fase1/venster-kosten.py <checkpoint> [stappen] [vensters]
  bv. venster-kosten.py fase1/z490-nu.pt 30 1024,1536
"""
import sys, time
sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinism
determinism.lock(20260808)
import torch
import bridge, learning, snapshot

PAD = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 30
VENSTERS = [int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "1024,1536").split(",")]

inhoud = snapshot.read(PAD, device="cuda")
L = learning.Learner(batch_size=64)
L.adopt_shape((inhoud.get("extra") or {}).get("vorm"))
stap = snapshot.restore(inhoud, L.core, L.optimizer, L.device)
extra = inhoud.get("extra") or {}
L.adopt_window(bridge.translate_spec(extra["vorm"]).get("window"))
L.restore(extra)
L.steps = stap
print(f"geladen: stap {stap}, venster {L.core.window}, geheugen {len(L.memory)}, "
      f"partij {L.batch_size}, bf16 {L.bf16}, hekken {L.deepest_per}")

s = stap + 1
uitkomst = {}
for venster in VENSTERS:
    if venster > L.core.window:
        L.adopt_window(venster)
    for _ in range(4):                       # opwarmen — telt niet mee
        L.work(s); s += 1
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter(); pogingen = 0
    for _ in range(N):
        r = L.work(s); s += 1
        pogingen += r["score"] is not None
    torch.cuda.synchronize()
    per_stap = (time.perf_counter() - t0) / N * 1000
    piek = torch.cuda.max_memory_allocated() / 1024**2
    uitkomst[venster] = per_stap
    print(f"venster {venster}: {per_stap:.0f} ms/stap ({pogingen} pogingen "
          f"in {N}) | VRAM-piek {piek:.0f} MB", flush=True)

basis = uitkomst[VENSTERS[0]]
for v, t in uitkomst.items():
    print(f"  {v}: {t / basis:.2f}× tegenover {VENSTERS[0]}")
