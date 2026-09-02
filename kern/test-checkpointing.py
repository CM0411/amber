"""
Tests activation checkpointing — the groundwork for a bigger Amber (E).

With checkpointing on, a block keeps only its input while learning and
recomputes the rest during the backward pass. The promise enforced here:
that changes **nothing** about what she learns — same loss, same weights,
bit for bit — while the VRAM peak drops. And answering (no grad, with the
cache) is untouched by the flag.

Run:  venv/bin/python kern/test-checkpointing.py
"""

import determinism                         # MUST come before torch
determinism.lock(777)

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
print("Test — activation checkpointing")
print("=" * 70)
print()

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def learner(flag, seed_step=1):
    # Same seed → same initial weights for both learners.
    determinism.begin_step(seed_step)
    core = network.Core(layers=4, width=128, heads=4, window=512)
    return learning.Learner(core=core, device=DEVICE, batch_size=16,
                            replay_share=0.0, bf16=False, checkpointing=flag)


material = world.learning_tasks("rekenen", 3, 48)

# --- 1. Same numbers, bit for bit -----------------------------------------------

print("--- The same numbers ---")
plain = learner(False)
saved = learner(True)
same_start = all(torch.equal(a, b) for a, b in
                 zip(plain.core.state_dict().values(),
                     saved.core.state_dict().values()))
check("both learners start from the same weights", same_start)
check("the flag sits on the core",
      plain.core.checkpointing is False and saved.core.checkpointing is True)

losses = []
for step in range(1, 4):
    determinism.begin_step(step)
    a = plain.learn(material[(step - 1) * 16: step * 16])
    determinism.begin_step(step)
    b = saved.learn(material[(step - 1) * 16: step * 16])
    losses.append((a, b))
same_loss = all(a == b for a, b in losses)
same_weights = all(torch.equal(a, b) for a, b in
                   zip(plain.core.state_dict().values(),
                       saved.core.state_dict().values()))
same_moments = all(
    torch.equal(plain.optimizer.state[p]["exp_avg"],
                saved.optimizer.state[q]["exp_avg"])
    for p, q in zip(plain.core.parameters(), saved.core.parameters()))
check("three learning steps: same losses, bit for bit",
      same_loss, " / ".join(f"{a:.6f}={b:.6f}" for a, b in losses))
check("and the same weights and optimizer moments afterwards",
      same_weights and same_moments)

# --- 2. Answering is untouched -------------------------------------------------

print()
print("--- Answering ---")
determinism.begin_step(50)
given_plain = plain.answer(material[:8], at_most=40)
determinism.begin_step(50)
given_saved = saved.answer(material[:8], at_most=40)
check("answering gives the same text with the flag on",
      given_plain == given_saved)

# --- 3. Less memory ---------------------------------------------------------------

print()
print("--- Memory ---")
if DEVICE == "cuda":
    def peak(flag, knobs=None):
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        determinism.begin_step(99)
        core = network.Core(layers=8, width=384, heads=6, window=1024)
        L = learning.Learner(core=core, device=DEVICE, batch_size=16,
                             replay_share=0.0, bf16=False, checkpointing=flag)
        if knobs is not None:
            # the P100 sprint's knobs (1 sep 2026): 0/0 is the bare road,
            # every block recomputed; the defaults keep what fits
            L.core.keep_below, L.core.light_below = knobs
        # a full-window batch: the case where the scratch work dominates
        chunk = world.learning_tasks("rekenen", 30, 16, room=1024 - 112)
        determinism.begin_step(100)
        L.learn(chunk)
        torch.cuda.synchronize()
        used = torch.cuda.max_memory_allocated() / 1024 ** 2
        del L, core
        torch.cuda.empty_cache()
        return used
    without = peak(False)
    with_ = peak(True, knobs=(0, 0))
    check("the VRAM peak drops with checkpointing (8 layers, window 1024, "
          "batch 16, bare road)", with_ < 0.75 * without,
          f"{without:.0f} MB → {with_:.0f} MB ({with_ / without:.0%})")
    # With the sprint's defaults small groups keep their scratch on purpose
    # (time for memory where memory is plenty); what must hold is that it
    # never costs more than no checkpointing at all.
    kept = peak(True)
    check("with the default knobs the peak never exceeds the plain path",
          kept <= 1.02 * without,
          f"{without:.0f} MB → {kept:.0f} MB ({kept / without:.0%})")
else:
    print("         (no GPU here — memory check skipped)")

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
