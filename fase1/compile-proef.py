"""De torch.compile-proef — meten, en pas geloven bij bit-voor-bit.

Draait op de trainer (Z490), op een rungrens, volledig in het geheugen.
Twee vragen, in deze volgorde van belang:

  1. blijft het determinisme staan? Twee identieke korte runs mét compile
     moeten bit voor bit dezelfde gewichten geven — anders gaat compile
     niet aan, hoeveel hij ook oplevert
  2. wat levert het op? stappen per seconde, met en zonder

  python3 fase1/compile-proef.py
"""
import copy
import sys
import time

sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinism
determinism.lock(20260808)

import torch
import bridge
import learning
import snapshot

PAD = "/home/arch/amber-werk/fase1/leven/momentopname.pt"


def bouw():
    determinism.begin_step(0)
    L = learning.Learner(batch_size=64)
    inhoud = snapshot.read(PAD, device=L.device)
    stap = snapshot.restore(inhoud, L.core, L.optimizer, L.device)
    extra = inhoud.get("extra") or {}
    if extra.get("vorm"):
        L.adopt_window(bridge.translate_spec(extra["vorm"]).get("window") or 0)
    if extra.get("geheugen"):
        L.restore(extra)
    L.steps = stap
    return L, stap


def vingerafdruk(core):
    import hashlib
    h = hashlib.sha256()
    for k in sorted(core.state_dict()):
        h.update(core.state_dict()[k].detach().cpu().numpy().tobytes())
    return h.hexdigest()[:16]


def stappen(L, vanaf, n):
    for s in range(vanaf + 1, vanaf + 1 + n):
        L.work(s)
    torch.cuda.synchronize()


print("== zonder compile ==")
L, stap = bouw()
stappen(L, stap, 5)                        # opwarmen
t0 = time.perf_counter()
stappen(L, stap + 5, 40)
zonder = (time.perf_counter() - t0) / 40 * 1000
print(f"{zonder:.0f} ms per stap")

print("== met compile: eerst het determinisme-bewijs ==")
afdrukken = []
for ronde in (1, 2):
    L, stap = bouw()
    L.core.forward = torch.compile(L.core.forward)
    stappen(L, stap, 20)
    afdrukken.append(vingerafdruk(L.core))
    print(f"  ronde {ronde}: {afdrukken[-1]}")
if afdrukken[0] != afdrukken[1]:
    print("GEEN BIT-GELIJKHEID — compile gaat NIET aan. Klaar.")
    sys.exit(1)
print("  bit voor bit gelijk — determinisme overleeft compile")

print("== met compile: het tempo ==")
L, stap = bouw()
L.core.forward = torch.compile(L.core.forward)
stappen(L, stap, 8)                        # opwarmen + compileren
t0 = time.perf_counter()
stappen(L, stap + 8, 40)
met = (time.perf_counter() - t0) / 40 * 1000
print(f"{met:.0f} ms per stap")
print(f"\nuitkomst: {zonder:.0f} -> {met:.0f} ms "
      f"({100 * (zonder - met) / zonder:.0f}% winst) en determinisme intact")
