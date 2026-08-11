"""
Tests the determinism module.

Not "does it run", but: does the latch do what it promises, and does the
assumption hold that the whole snapshot format rests on — that resuming
from step N gives the same sequence as running through to N.

Run:  venv/bin/python kern/test-determinism.py
"""

import determinism             # MUST come before torch — the module guards this

import subprocess
import sys

import torch

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
print("Test — determinism")
print("=" * 70)
print()

# --- 1. The latch ----------------------------------------------------------
# The module must refuse when torch is already loaded: by then
# CUBLAS_WORKSPACE_CONFIG has no effect and determinism is silently half off.

print("--- The latch ---")
r = subprocess.run(
    [sys.executable, "-c", "import torch; import determinism"],
    capture_output=True, text=True, cwd="/home/arch/amber-werk/kern",
    env={"PATH": "/usr/bin"},
)
check(
    "importing after torch is refused",
    r.returncode != 0 and "after torch was already loaded" in r.stderr,
    "the module does not let itself be loaded too late in silence",
)

print()

# --- 2. Switching on and checking back -------------------------------------

print("--- Switching on ---")
state = determinism.lock(1234)
check("lock() passes its own verification", True)
check(
    "deterministic algorithms are on",
    state["deterministic_algorithms"] is True,
)
check("cudnn.benchmark is off", state["cudnn_benchmark"] is False,
      "otherwise it picks a different algorithm per run")
check("CUBLAS_WORKSPACE_CONFIG is set correctly",
      state["cublas_workspace"] == ":4096:8")

# The verification must also really trip when someone turns it off later.
torch.backends.cudnn.benchmark = True
try:
    determinism.verify()
    caught = False
except RuntimeError:
    caught = True
finally:
    torch.backends.cudnn.benchmark = False
check("verify() catches a setting flipped afterwards", caught,
      "a latch that does not clamp is not a latch")

print()

# --- 3. The derivation is portable -----------------------------------------

print("--- The derivation ---")
a = determinism.seed_for_step(7)
b = determinism.seed_for_step(7)
check("the same step number gives the same seed", a == b)
check("different steps give different seeds",
      determinism.seed_for_step(7) != determinism.seed_for_step(8))
check("the seed fits what torch accepts", 0 <= a < 2**63)
seeds = {determinism.seed_for_step(i) for i in range(2000)}
check("2000 consecutive steps give 2000 different seeds",
      len(seeds) == 2000, f"{len(seeds)} unique values")

print()

# --- 4. What it is all about: resuming ~ running through -------------------
# This is the assumption the whole snapshot format rests on. If it does not
# hold, (seed, step number) is not enough and generator state would have to
# come along after all — exactly what we do not want.

print("--- Resuming versus running through ---")

device = "cuda" if torch.cuda.is_available() else "cpu"


def sequence(steps, start=0):
    """Mimics a learning loop: every step draws randomness and computes."""
    out = []
    for step in range(start, steps):
        determinism.begin_step(step)
        x = torch.randn(64, 64, device=device)
        layer = torch.nn.Linear(64, 64).to(device)
        y = (layer(x).relu() * torch.randn(64, 64, device=device)).sum()
        out.append(y.detach().clone())
    return out


straight = sequence(10)
again = sequence(10)
check("two full runs are bit for bit equal",
      all(torch.equal(p, q) for p, q in zip(straight, again)))

resumed = sequence(10, start=5)
check(
    "resuming from step 5 gives exactly what running through gave there",
    all(torch.equal(p, q) for p, q in zip(straight[5:], resumed)),
    "this is what justifies keeping only (seed, step number) instead of "
    "device-specific generator state",
)

# And a different seed must give something different, or the above proves
# nothing.
determinism.lock(9999)
different = sequence(3)
determinism.lock(1234)
check("a different seed gives a different sequence",
      not any(torch.equal(p, q) for p, q in zip(straight[:3], different)))

print()

# --- 5. What goes into the snapshot ----------------------------------------

print("--- The state that goes into the snapshot ---")
s = determinism.state()
check("contains only numbers, text and booleans",
      all(isinstance(v, (int, str, bool, type(None))) for v in s.values()),
      "nothing device-bound, or the snapshot is not portable")
for k, v in s.items():
    print(f"         {k}: {v}")

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
