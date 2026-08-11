"""
Tests the growing of the window — the heart of phase 2.

The promise enforced here: a larger window changes nothing about who she
already is. Same input, same output, bit for bit — and her snapshot from
before the growth moves along without losing one parameter. This is why
the positions go by rotation and not by a learned table: a table would
have meant new, untrained parameters here and therefore a different
Amber.

Run:  venv/bin/python kern/test-window-growth.py
"""

import determinism                         # MUST come before torch
determinism.lock(1234)

import os
import sys
import tempfile

import torch

import network
import snapshot

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
print("Test — window growth")
print("=" * 70)
print()

# A small network is enough: the property does not depend on the size.
core = network.Core(layers=2, width=64, heads=4, window=64)
core.eval()

determinism.begin_step(1)
inputs = torch.randint(0, 260, (2, 64))    # exactly the old window full

with torch.no_grad():
    before, _ = core.advance(inputs)

# --- 1. Growing does not change the output ---------------------------------

print("--- Growing does not change her ---")
core.grow_window(96)
with torch.no_grad():
    after, _ = core.advance(inputs)
check("output after growth bit for bit equal", torch.equal(before, after),
      "same input, window 64 -> 96")
check("the spec reports the new window", core.spec()["window"] == 96)
check("parameters unchanged by growth",
      core.spec()["parameters"] == network.Core(
          layers=2, width=64, heads=4, window=64).spec()["parameters"],
      "window growth adds no parameters — that is the whole point")

# --- 2. The new territory is really open -----------------------------------

print()
print("--- The new territory ---")
long_seq = torch.randint(0, 260, (1, 96))
with torch.no_grad():
    out_long, _ = core.advance(long_seq)
check("a sequence longer than the old window is now allowed",
      out_long.shape[1] == 96)

too_long = torch.randint(0, 260, (1, 97))
try:
    core.advance(too_long)
    check("beyond the new window refuses", False)
except ValueError:
    check("beyond the new window refuses", True)

# --- 3. Shrinking refuses --------------------------------------------------

print()
print("--- Shrinking ---")
try:
    core.grow_window(64)
    check("shrinking refuses", False)
except ValueError:
    check("shrinking refuses", True,
          "a smaller window can make lived experiences unreadable")

# --- 4. Her snapshot moves along -------------------------------------------

print()
print("--- The snapshot moves along ---")
old = network.Core(layers=2, width=64, heads=4, window=64)
old.eval()
with torch.no_grad():
    old_out, _ = old.advance(inputs)

with tempfile.TemporaryDirectory() as folder:
    path = os.path.join(folder, "proef.pt")
    snapshot.write(path, step=7, model=old, extra={"vorm": old.spec()})
    content = snapshot.read(path)

    fresh = network.Core.from_spec(content["extra"]["vorm"])
    snapshot.restore(content, model=fresh)
    fresh.eval()
    fresh.grow_window(96)

    with torch.no_grad():
        fresh_out, _ = fresh.advance(inputs)
    check("loaded + grown gives the same output as the original",
          torch.equal(old_out, fresh_out),
          "the run-3 snapshot can enter run 4 with a larger window")
    check("the growth lands in the next snapshot",
          fresh.spec()["window"] == 96)

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(1 if failed else 0)
