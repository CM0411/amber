"""
Tests the fixed KV cache — the answering path (15 Aug 2026).

While she writes, every layer keeps the keys and values of what stands
before. That cache is now laid out once at full length and written into in
place, instead of copied into a larger block for every character. Enforced
here: writing character by character against the cache gives the same
scores as one full pass; the buffer never moves; a full cache refuses; and
the Learner's batched answering still equals answering one by one.

Run:  venv/bin/python kern/test-cache.py
"""

import determinism                         # MUST come before torch
determinism.lock(2718)

import sys

import torch

import learning
import network
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
print("Test — the fixed KV cache")
print("=" * 70)
print()

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
core = network.Core(layers=3, width=96, heads=4, window=128).to(DEVICE)
core.eval()

# --- 1. Character by character equals one full pass ------------------------

print("--- The same scores ---")
determinism.begin_step(1)
codes = torch.randint(0, 260, (5, 40), device=DEVICE)
with torch.no_grad():
    full, _ = core.advance(codes)                       # (5, 40, vocab)
    cache = core.new_cache(64)
    part, cache = core.advance(codes[:, :30], cache=cache)
    incremental = [part[:, -1]]
    for pos in range(30, 40):
        scores, cache = core.advance(codes[:, pos:pos + 1], cache=cache,
                                     offset=pos)
        incremental.append(scores[:, -1])
inc = torch.stack(incremental[1:], dim=1)               # positions 30..39
ref = full[:, 30:40]
check("ten characters against the cache match the full pass "
      "(same argmax, scores within 1e-4)",
      torch.equal(inc.argmax(-1), ref.argmax(-1))
      and torch.allclose(inc, ref, atol=1e-4, rtol=1e-4),
      f"largest difference {float((inc - ref).abs().max()):.2e}")
check("the cache knows how far it is", all(c.n == 40 for c in cache))

# --- 2. The buffer never moves --------------------------------------------------

print()
print("--- The buffer ---")
ptr_before = [c.k.data_ptr() for c in cache]
with torch.no_grad():
    for pos in range(40, 50):
        _, cache = core.advance(codes[:, :1], cache=cache, offset=pos)
ptr_after = [c.k.data_ptr() for c in cache]
check("ten more characters: the same memory, nothing copied",
      ptr_before == ptr_after and all(c.n == 50 for c in cache))
check("the buffer holds exactly `capacity` positions",
      all(c.k.shape[2] == 64 for c in cache))

full_refused = False
try:
    with torch.no_grad():
        for pos in range(50, 70):
            _, cache = core.advance(codes[:, :1], cache=cache, offset=pos)
except ValueError:
    full_refused = True
check("a full cache refuses instead of overflowing", full_refused)

# --- 3. Through the Learner ------------------------------------------------------

print()
print("--- Through the Learner ---")
determinism.begin_step(2)
L = learning.Learner(core=network.Core(layers=2, width=64, heads=4,
                                       window=256),
                     device=DEVICE, batch_size=8, replay_share=0.0,
                     bf16=False)
material = world.learning_tasks("rekenen", 2, 12)
determinism.begin_step(3)
together = L.answer(material, at_most=60)
determinism.begin_step(3)
alone = [L.answer([t], at_most=60)[0] for t in material]
check("batched answering equals answering one by one",
      together == alone, f"{sum(a == b for a, b in zip(together, alone))}/12")
check("every answer is text of bounded length",
      all(isinstance(a, str) and len(a) <= 60 for a in together))

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
