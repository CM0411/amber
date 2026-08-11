"""
Tests the key bridge — does her brain survive the English rename?

The Dutch modules are gone; what remains is their trace: every snapshot
written before 11 Aug 2026 carries Dutch weight keys. The bridge must
carry those into the English core, forever. Proven two ways:

  * a round trip: English keys renamed to their Dutch originals with the
    bridge's own table, then translated back in — strict, and the output
    bit for bit equal
  * her real run-3 snapshot (fase1/nu.pt), when it stands there: loads
    into the English core through the ordinary snapshot.restore path, and
    can grow its window afterwards

Run:  venv/bin/python kern/test-bridge.py
"""

import determinism                         # MUST come before torch
determinism.lock(1234)

import os
import sys

import torch

import bridge
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
print("Test — key bridge (Dutch snapshot -> English core)")
print("=" * 70)
print()

# --- 1. Round trip on fresh weights ----------------------------------------
# The Dutch core no longer exists, so the Dutch side is reconstructed from
# the bridge's own table: rename every English key back to its Dutch
# original. If the bridge is complete, translating that forward loads
# strict — and the network is bit for bit the same one.

print("--- Round trip on fresh weights ---")
core = network.Core(layers=3, width=96, heads=4, window=128)
core.eval()

dutch_state = {}
for key, value in core.state_dict().items():
    for old, new in bridge._WEIGHT_KEYS:
        key = key.replace(new, old)
    dutch_state[key] = value

check("the reconstructed past really is Dutch",
      bridge.is_dutch_state(dutch_state)
      and not bridge.is_dutch_state(core.state_dict()))

twin = network.Core(layers=3, width=96, heads=4, window=128)
twin.load_state_dict(bridge.translate_state(dutch_state), strict=True)
twin.eval()
check("every Dutch key finds its English place", True,
      "load_state_dict strict=True would have refused otherwise")

determinism.begin_step(1)
inputs = torch.randint(0, 260, (3, 128))
with torch.no_grad():
    out_a = core.advance(inputs)[0]
    out_b = twin.advance(inputs)[0]
check("same input, same output, bit for bit", torch.equal(out_a, out_b))

english_state = core.state_dict()
check("English input passes the bridge untouched",
      bridge.translate_state(english_state) is english_state,
      "the same object comes back, no copy and no renaming")

# --- 2. The spec crosses too -----------------------------------------------

print()
print("--- The spec ---")
dutch_spec = {"lagen": 3, "breedte": 96, "koppen": 4, "venster": 128,
              "parameters": core.parameter_count()}
translated = bridge.translate_spec(dutch_spec)
check("a Dutch spec becomes an English one",
      translated["layers"] == 3 and translated["window"] == 128)
check("an English spec passes unchanged (idempotent)",
      bridge.translate_spec(translated) == translated)
rebuilt = network.Core.from_spec(bridge.translate_spec(dutch_spec))
check("and the core can be rebuilt from it",
      rebuilt.spec()["parameters"] == core.parameter_count())

# --- 3. Her real snapshot, when it stands there ----------------------------

print()
print("--- Her real snapshot ---")
PATH = "/home/arch/amber-werk/fase1/nu.pt"
if os.path.exists(PATH):
    content = snapshot.read(PATH)
    vorm = (content.get("extra") or {}).get("vorm") or {
        "lagen": 8, "breedte": 384, "koppen": 6, "venster": 512}
    real = network.Core.from_spec(bridge.translate_spec(vorm))
    snapshot.restore(content, real, None)     # runs the bridge inside
    real.eval()

    determinism.begin_step(2)
    probe = torch.randint(0, 260, (2, real.window))
    with torch.no_grad():
        out = real.advance(probe)[0]
    check("her run-3 weights load through the ordinary restore path",
          out.shape == (2, real.window, 260)
          and bridge.is_dutch_state(content["model"]),
          f"snapshot of step {content.get('stap', '?')}, Dutch keys on disk, "
          f"full window forward pass")
    check("and the English core can simply grow afterwards",
          (real.grow_window(max(768, real.window)) or real.window >= 768))
else:
    print("         (no snapshot found — skipped)")

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
