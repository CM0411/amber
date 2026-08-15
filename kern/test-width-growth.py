"""
Tests growing wider — the second half of E (16 Aug 2026).

Depth was there since 15 Aug (test-layer-growth.py). Width is the other
axis, and it is trickier: the residual width cannot grow without moving
every old number through LayerNorm's average, so "wider" here means more
attention heads and more feedforward units *inside* the blocks, with the
stream itself untouched. New heads and units come in behind zero columns
(`out`, `down`): they compute, but add exactly nothing until they have
learned to — the same idea as the zero gate on a new block.

Enforced here:
  * growing changes nothing about who she is — same input, same output
  * the old moments survive in their old slots, the new slots start at zero,
    the step count is kept; untouched parameters keep their moments
  * after one step the new heads and units carry moments and have moved
  * a wider snapshot loads into a fresh Learner via adopt_shape, and after
    that both learn bit for bit the same
  * old snapshots (no head_size / hidden in the spec) still describe the
    same net; the residual width and the head size refuse to change;
    nets do not shrink

Run:  venv/bin/python kern/test-width-growth.py
"""

import determinism                         # MUST come before torch
determinism.lock(8765)

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
print("Test — width growth")
print("=" * 70)
print()

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def small_learner():
    core = network.Core(layers=2, width=64, heads=4, window=256)
    return learning.Learner(core=core, device=DEVICE, batch_size=8,
                            replay_share=0.0, bf16=False)


material = world.learning_tasks("rekenen", 1, 24)


def max_diff(a, b):
    return float((a - b).abs().max())


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
                   L.optimizer.state[p]["exp_avg_sq"].clone(),
                   L.optimizer.state[p]["step"].clone())
               for p in old_params if p in L.optimizer.state}
old_shapes = {p: tuple(p.shape) for p in old_params}
old_spec = L.core.spec()

transplants = L.grow_width(heads=6, hidden=512)      # 4 → 6 heads, 256 → 512
L.core.eval()
with torch.no_grad():
    after, _ = L.core.advance(inputs)
check("wider (6 heads, 512 hidden): same input, same output, bit for bit",
      torch.equal(before, after), f"largest difference {max_diff(before, after):.3g}")
check("the spec says 6 heads × 512 hidden, head size unchanged",
      L.core.spec()["heads"] == 6 and L.core.spec()["hidden"] == 512
      and L.core.spec()["head_size"] == old_spec["head_size"] == 16)
check("more parameters, same width and layers",
      L.core.spec()["parameters"] > old_spec["parameters"]
      and L.core.spec()["width"] == 64 and L.core.spec()["layers"] == 2)
check("the answer copy follows the shape",
      L._answer_core.spec() == L.core.spec())
new_out_zero = all(torch.equal(b.attention.out.weight[:, 64:],
                               torch.zeros_like(b.attention.out.weight[:, 64:]))
                   for b in L.core.blocks)
new_down_zero = all(torch.equal(b.feedforward.down.weight[:, 256:],
                                torch.zeros_like(b.feedforward.down.weight[:, 256:]))
                    for b in L.core.blocks)
check("new heads and units sit behind zero columns", new_out_zero and new_down_zero)

# also: growing one axis at a time, and in a net that answers with a cache
core2 = network.Core(layers=2, width=64, heads=4, window=256).to(DEVICE).eval()
with torch.no_grad():
    cache = core2.new_cache(64)
    q = inputs[:, :40]
    s1, _ = core2.advance(q, cache=cache)
    s2, _ = core2.advance(inputs[:, 40:41], cache=cache, offset=40)
    core2.grow_heads(2)
    cache = core2.new_cache(64)
    t1, _ = core2.advance(q, cache=cache)
    t2, _ = core2.advance(inputs[:, 40:41], cache=cache, offset=40)
check("heads only, on the answering path with cache: bit for bit",
      torch.equal(s1, t1) and torch.equal(s2, t2))
with torch.no_grad():
    core2.grow_hidden(300)
    u1, _ = core2.advance(inputs)
    core2b = network.Core(layers=2, width=64, heads=4, window=256).to(DEVICE).eval()
check("hidden only, an odd size (300): still the same net", core2.hidden == 300
      and torch.equal(core2.advance(q)[0], s1))

# and at her real shape (8 × 384, 6 heads, window 1024): a different size
# can make cuBLAS pick another kernel with another summation order, so the
# small net proves nothing about the big one
if DEVICE == "cuda":
    big = network.Core(layers=8, width=384, heads=6, window=1024).to(DEVICE).eval()
    determinism.begin_step(20)
    long_inputs = torch.randint(0, 260, (4, 512), device=DEVICE)
    with torch.no_grad():
        b1, _ = big.advance(long_inputs)
        big.grow_heads(2)                       # 6 → 8 heads
        big.grow_hidden(2048)                   # 1536 → 2048
        b2, _ = big.advance(long_inputs)
    check("at the run shape (8×384 → 8 heads, 2048 hidden), batch 4 × 512: "
          "bit for bit", torch.equal(b1, b2),
          f"largest difference {max_diff(b1, b2):.3g}")
    del big, b1, b2

# --- 2. The optimizer ---------------------------------------------------------

print()
print("--- The optimizer ---")
replaced = {old: (new, place) for old, new, place in transplants}
replaced_ids = {id(o) for o in replaced}
untouched = [p for p in old_params if id(p) not in replaced_ids]
kept = all(p in L.optimizer.state
           and torch.equal(L.optimizer.state[p]["exp_avg"], m[0])
           and torch.equal(L.optimizer.state[p]["exp_avg_sq"], m[1])
           for p, m in old_moments.items() if id(p) not in replaced_ids)
check("untouched parameters keep their moments by identity",
      kept and len(untouched) > 0, f"{len(untouched)} parameters")


def carried_right(old, new, place):
    st = L.optimizer.state.get(new)
    if st is None:
        return False
    for key in ("exp_avg", "exp_avg_sq"):
        want = torch.zeros_like(new)
        place(old_moments[old][0 if key == "exp_avg" else 1], want)
        if not torch.equal(st[key], want):
            return False
    return torch.equal(st["step"], old_moments[old][2])


check("replaced parameters: old moments in the old slots, zeros in the new, "
      "step kept",
      all(carried_right(o, n, pl) for o, (n, pl) in replaced.items())
      and len(replaced) == 8, f"{len(replaced)} replaced tensors")
check("one parameter group, all parameters in it, none of the old shapes left",
      len(L.optimizer.param_groups) == 1
      and len(L.optimizer.param_groups[0]["params"]) == len(list(L.core.parameters()))
      and all(tuple(n.shape) != old_shapes[o] for o, (n, _) in replaced.items()))

L.core.train()
determinism.begin_step(11)
L.learn(material[8:16])
moved = all(not torch.equal(b.attention.out.weight[:, 64:],
                            torch.zeros_like(b.attention.out.weight[:, 64:]))
            and not torch.equal(b.feedforward.down.weight[:, 256:],
                                torch.zeros_like(b.feedforward.down.weight[:, 256:]))
            for b in L.core.blocks)
check("after one step the new columns moved off zero", moved)

# --- 3. The snapshot round trip ---------------------------------------------

print()
print("--- The snapshot ---")
with tempfile.TemporaryDirectory() as folder:
    path = os.path.join(folder, "wider.pt")
    snapshot.write(path, 11, L.core, L.optimizer, {"zaad": 8765},
                   extra={"vorm": L.core.spec()})
    content = snapshot.read(path, device=DEVICE)

    fresh = small_learner()
    refused = False
    try:
        snapshot.restore(content, fresh.core, fresh.optimizer, DEVICE)
    except Exception:
        refused = True
    check("without adopt_shape a fresh narrow net refuses the snapshot", refused)

    fresh = small_learner()
    fresh.adopt_shape((content.get("extra") or {}).get("vorm"))
    stap = snapshot.restore(content, fresh.core, fresh.optimizer, DEVICE)
    same_weights = all(torch.equal(a, b) for a, b in
                       zip(L.core.state_dict().values(),
                           fresh.core.state_dict().values()))
    check("with adopt_shape it loads: 6 heads × 512 hidden, weights bit for bit",
          stap == 11 and fresh.core.spec() == L.core.spec() and same_weights)

    determinism.begin_step(12)
    a = L.learn(material[16:24])
    determinism.begin_step(12)
    b = fresh.learn(material[16:24])
    same_after = all(torch.equal(x, y) for x, y in
                     zip(L.core.state_dict().values(),
                         fresh.core.state_dict().values()))
    check("one more step on both: same loss, same weights",
          a == b and same_after, f"loss {a:.6f} / {b:.6f}")

# --- 4. Old snapshots and what refuses ---------------------------------------

print()
print("--- Old specs and what refuses ---")
old_style = {"layers": 2, "width": 64, "heads": 4, "window": 256}
rebuilt = network.Core.from_spec(old_style)
check("a spec without head_size/hidden rebuilds the same shape as before",
      rebuilt.head_size == 16 and rebuilt.hidden == 256
      and rebuilt.spec()["parameters"] == network.Core(
          layers=2, width=64, heads=4, window=256).spec()["parameters"])
plain = small_learner()
plain.adopt_shape(old_style)
check("adopt_shape on an old-style spec grows nothing",
      plain.core.spec()["heads"] == 4 and plain.core.spec()["hidden"] == 256)

narrower = False
try:
    fresh.adopt_shape({"layers": 2, "width": 64, "heads": 4, "hidden": 256,
                       "head_size": 16, "window": 256})
except ValueError:
    narrower = True
check("adopt_shape refuses fewer heads / hidden units", narrower)
other_size = False
try:
    fresh.adopt_shape({"layers": 2, "width": 64, "heads": 8, "head_size": 8,
                       "hidden": 512, "window": 256})
except ValueError:
    other_size = True
check("adopt_shape refuses another head size", other_size)
wider_stream = False
try:
    fresh.adopt_shape({"layers": 2, "width": 128, "heads": 8, "head_size": 16,
                       "hidden": 512, "window": 256})
except ValueError:
    wider_stream = True
check("adopt_shape refuses another residual width", wider_stream)
bad = False
try:
    fresh.core.grow_hidden(512)             # not more than it has
except ValueError:
    bad = True
check("grow_hidden refuses a size that is not larger", bad)
check("the Dutch spec keys go through the bridge",
      bridge.translate_spec({"lagen": 2, "breedte": 64, "koppen": 6,
                             "kopgrootte": 16, "verborgen": 512,
                             "venster": 256}).get("hidden") == 512)

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
