"""
Tests the growing of a layer — the groundwork of phase 5 (E).

The core could already insert a block whose gates stand at zero (the output
does not change, bit for bit). What was missing is everything around it:
the optimizer that must keep the moments of the old weights, the answer
copy on the second card, and the snapshot that must load into a fresh
Learner of the right depth. Each of those breaks quietly, and quiet
breakage is what this project hunts.

Enforced here:
  * growing changes nothing about who she is — same input, same output
  * the old moments survive; the new block starts empty and then learns
  * a grown snapshot loads into a fresh Learner via adopt_shape, and after
    that both learn bit for bit the same
  * shrinking and width changes refuse

Run:  venv/bin/python kern/test-layer-growth.py
"""

import determinism                         # MUST come before torch
determinism.lock(4321)

import os
import sys
import tempfile

import torch

import bridge
import learning
import network
import snapshot
import world

passed = 0
failed = 0


def check(name, good, note=""):
    global passed, failed
    if good:
        passed += 1
        print(f"[  OK  ] {name}")
    else:
        failed += 1
        print(f"[ FAIL ] {name}")
    if note:
        print(f"         {note}")


print("=" * 70)
print("Test — layer growth")
print("=" * 70)
print()

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def small_learner():
    core = network.Core(layers=2, width=64, heads=4, window=256)
    return learning.Learner(core=core, device=DEVICE, batch_size=8,
                            replay_share=0.0, bf16=False)


material = world.learning_tasks("rekenen", 1, 24)
probe = material[:8]

# --- 1. Growing does not change her -----------------------------------------

print("--- Growing does not change her ---")
L = small_learner()
for step in range(1, 4):                   # some learning first: real moments
    determinism.begin_step(step)
    L.learn(material[:8])
L.core.eval()
determinism.begin_step(10)
inputs = torch.randint(0, 260, (2, 128), device=DEVICE)
with torch.no_grad():
    before, _ = L.core.advance(inputs)

old_params = list(L.core.parameters())
old_moments = {p: (L.optimizer.state[p]["exp_avg"].clone(),
                   L.optimizer.state[p]["exp_avg_sq"].clone())
               for p in old_params if p in L.optimizer.state}
new_block = L.grow_layer()
L.core.eval()
with torch.no_grad():
    after, _ = L.core.advance(inputs)
check("a third block: same input, same output, bit for bit",
      torch.equal(before, after))
check("the spec now says three layers", L.core.spec()["layers"] == 3)
check("the answer copy follows the shape",
      len(L._answer_core.blocks) == 3)

# --- 2. The optimizer keeps the old moments ---------------------------------

print()
print("--- The optimizer ---")
kept = all(p in L.optimizer.state
           and torch.equal(L.optimizer.state[p]["exp_avg"], m[0])
           and torch.equal(L.optimizer.state[p]["exp_avg_sq"], m[1])
           for p, m in old_moments.items())
check("every old moment survives the growth, bit for bit",
      kept and len(old_moments) > 0, f"{len(old_moments)} parameters")
check("one parameter group, all parameters in it",
      len(L.optimizer.param_groups) == 1 and
      len(L.optimizer.param_groups[0]["params"]) ==
      len(list(L.core.parameters())))
new_params = list(new_block.parameters())
check("the new block starts with no moments",
      all(p not in L.optimizer.state for p in new_params))
check("its gates stand at zero",
      float(new_block.alpha1) == 0.0 and float(new_block.alpha2) == 0.0)

L.core.train()
determinism.begin_step(11)
L.learn(material[8:16])
check("after one step the new block has moments and its gates moved",
      all(p in L.optimizer.state for p in new_params)
      and (float(new_block.alpha1) != 0.0 or float(new_block.alpha2) != 0.0))

# --- 3. The snapshot round trip ---------------------------------------------

print()
print("--- The snapshot ---")
with tempfile.TemporaryDirectory() as folder:
    path = os.path.join(folder, "grown.pt")
    snapshot.write(path, 11, L.core, L.optimizer, {"zaad": 4321},
                   extra={"vorm": L.core.spec()})
    content = snapshot.read(path, device=DEVICE)

    fresh = small_learner()                # two layers, like the run began
    refused = False
    try:
        snapshot.restore(content, fresh.core, fresh.optimizer, DEVICE)
    except Exception:
        refused = True
    check("without adopt_shape a fresh two-layer net refuses the snapshot",
          refused)

    fresh = small_learner()
    fresh.adopt_shape((content.get("extra") or {}).get("vorm"))
    stap = snapshot.restore(content, fresh.core, fresh.optimizer, DEVICE)
    same_weights = all(torch.equal(a, b) for a, b in
                       zip(L.core.state_dict().values(),
                           fresh.core.state_dict().values()))
    check("with adopt_shape it loads: three layers, weights bit for bit",
          stap == 11 and len(fresh.core.blocks) == 3 and same_weights)
    check("the window travels along", fresh.core.window == L.core.window)

    # and both learn the same from here — moments included
    determinism.begin_step(12)
    a = L.learn(material[16:24])
    determinism.begin_step(12)
    b = fresh.learn(material[16:24])
    same_after = all(torch.equal(x, y) for x, y in
                     zip(L.core.state_dict().values(),
                         fresh.core.state_dict().values()))
    check("one more step on both: same loss, same weights",
          a == b and same_after, f"loss {a:.6f} / {b:.6f}")

# --- 4. What refuses ---------------------------------------------------------

print()
print("--- What refuses ---")
shrunk = False
try:
    fresh.adopt_shape({"layers": 2, "width": 64, "heads": 4, "window": 256})
except ValueError:
    shrunk = True
check("adopt_shape refuses fewer layers", shrunk)
wider = False
try:
    fresh.adopt_shape({"layers": 3, "width": 128, "heads": 4, "window": 256})
except ValueError:
    wider = True
check("adopt_shape refuses another width", wider)
check("the Dutch spec keys go through the bridge",
      bridge.translate_spec({"lagen": 3, "breedte": 64, "koppen": 4,
                             "venster": 256}).get("layers") == 3)

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
