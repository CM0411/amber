"""Herhaalbaarheidsbewijs — het meetpunt van fase 1, op de machine die traint.

Determinisme staat aan vanaf de eerste regel code, en op de P100's is het
bewezen: honderd stappen, afsluiten, herstarten, bit voor bit gelijk. Maar
de Z490 rekent op een RTX 3070 Ti in bf16 met een nieuwere torch, en dáár
is het nooit gemeten (15 aug 2026). Een leerrun waarvan je niet weet of hij
herhaalbaar is, is een run waarvan je de metingen niet kunt vertrouwen.

Dit script leest de momentopname zoals life.py dat doet, doet N echte
stappen (`Learner.work`, mét pogingen en herhaling uit haar geheugen) en
drukt één controlesom af over álle gewichten én de optimizertoestand. Het
schrijft niets: geen checkpoint, geen logboek. rungrens.py draait het
twee keer in twee losse processen en vergelijkt de twee sommen — twee
processen, niet twee lussen in één proces, want de vraag is of een
herstart bit voor bit uitkomt.

  python3 herhaalproef.py <momentopname> [stappen=50]
"""
import hashlib
import os
import sys

sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinism
determinism.lock(20260808)               # hetzelfde zaad als life.py
import torch
import learning, parallel, snapshot
# Under torchrun (two cards as two processes, 16 Aug 2026) every process
# takes its own card and its share; without torchrun this is a no-op. Both
# processes print their sum: DDP is repeatable when the two runs agree.
parallel.start()

PAD = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 50

inhoud = snapshot.read(PAD, device="cuda")
extra = inhoud.get("extra") or {}
# dezelfde machine-instelling als de dienst (rungrens geeft hem mee)
L = learning.Learner(batch_size=64,
                     checkpointing=os.environ.get("AMBER_CHECKPOINTING") == "1")
L.adopt_shape(extra.get("vorm"))
stap = snapshot.restore(inhoud, L.core, L.optimizer, L.device)
# Same order as life.py: the step number first, then the carried state —
# a snapshot that carries the optimizer-step counter (16 aug 2026) wins.
L.steps = stap
L.restore(extra)
print(f"geladen: stap {stap}, venster {L.core.window}, lagen "
      f"{len(L.core.blocks)}, geheugen {len(L.memory)}, bf16 {L.bf16}, "
      f"checkpointing {L.core.checkpointing}",
      flush=True)

for s in range(stap + 1, stap + 1 + N):
    L.work(s)
torch.cuda.synchronize()

h = hashlib.sha256()
for naam, w in L.core.state_dict().items():
    h.update(naam.encode())
    h.update(w.detach().to("cpu").contiguous().view(torch.uint8).numpy().tobytes())
for p in L.core.parameters():
    st = L.optimizer.state.get(p)
    if not st:
        continue
    for k in ("exp_avg", "exp_avg_sq"):
        h.update(st[k].detach().to("cpu").contiguous().view(torch.uint8).numpy().tobytes())
print(f"controlesom na {N} stappen: {h.hexdigest()[:24]}"
      + (f"  (proces {parallel.rank()} van {parallel.world()})" if parallel.active() else ""))
parallel.stop()
