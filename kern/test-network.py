"""
Tests the character set and the learning core.

Two properties weigh heaviest here, and neither can be built in later:

  * **growing does not change the output** — bit for bit, not roughly
  * the character set and the positions are fixed in a way that never
    needs revisiting

Run:  venv/bin/python kern/test-network.py
"""

import determinism                         # MUST come before torch
determinism.lock(1234)

import sys

import torch

import network
import tasks
import tokens

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
print("Test — character set and learning core")
print("=" * 70)
print()

# --- 1. The character set --------------------------------------------------

print("--- The character set ---")
check("text goes through it there and back",
      tokens.decode(tokens.encode("47 * 13")) == "47 * 13")
check("Dutch with accents fits without ado",
      tokens.decode(tokens.encode("één café, zéér véél")) == "één café, zéér véél",
      "bytes never need extending")
check("digits stay separate characters",
      len(tokens.encode("47")) == 2,
      "no tokenizer that glues '47' into one chunk — that makes arithmetic "
      "artificially hard")

t = tasks.make("rekenen", 3, 5)
seq, counts = tokens.task_to_sequence(t)
check("a task becomes QUESTION problem ANSWER solution END",
      seq[0] == tokens.QUESTION and tokens.ANSWER in seq
      and seq[-1] == tokens.END,
      tokens.show(seq))

marked = [c for c, m in zip(seq, counts) if m]
check(
    "the loss counts only over the answer and the END token",
    tokens.decode(marked) == t.solution and marked[-1] == tokens.END
    and not any(counts[:seq.index(tokens.ANSWER) + 1]),
    "otherwise she learns to invent questions instead of answering them",
)

check("the answer can be pulled back out",
      tokens.answer_from_sequence(seq) == t.solution)
check("half an answer yields nothing", tokens.answer_from_sequence([1, 2, 3]) == "",
      "better empty than half")

seqs, masks = tokens.batch([[1, 2, 3], [1, 2]], [[True] * 3, [True] * 2])
check("padding counts nowhere",
      seqs[1][-1] == tokens.PAD and masks[1][-1] is False,
      "otherwise she learns to predict padding and the loss looks fine")

print()

# --- 2. The network runs ---------------------------------------------------

print("--- The network ---")
core = network.Core(layers=4, width=128, heads=4, window=64)
codes = torch.randint(0, 255, (2, 32))
out = core(codes)
check("the output has the right shape",
      tuple(out.shape) == (2, 32, tokens.VOCAB),
      f"{tuple(out.shape)} — one score per character of the set")

check("the parameter count is counted",
      core.parameter_count() > 0,
      f"{core.parameter_count():,} in this small trial set-up")

# Causal: a character may not look into the future. Change the last
# character and everything before it must stay exactly equal.
a = codes.clone()
b = codes.clone()
b[:, -1] = (b[:, -1] + 7) % 255
out_a, out_b = core(a), core(b)
check(
    "a character never looks ahead",
    torch.equal(out_a[:, :-1], out_b[:, :-1]),
    "changing the last character leaves everything before it bit for bit",
)

print()

# --- 3. What it is about: growing changes nothing --------------------------

print("--- Growing ---")
core = network.Core(layers=4, width=128, heads=4, window=64)
core.eval()
codes = torch.randint(0, 255, (2, 32))
with torch.no_grad():
    before = core(codes).clone()

spec_before = core.spec()
core.add_block()
with torch.no_grad():
    after = core(codes)

check(
    "an extra layer leaves the output BIT FOR BIT equal",
    torch.equal(before, after),
    "no approximation: x + 0 * something is exactly x. Without this E "
    "measures damage, not growth",
)
check("and a layer really was added",
      core.spec()["layers"] == spec_before["layers"] + 1
      and core.parameter_count() > spec_before["parameters"],
      f"{spec_before['layers']} → {core.spec()['layers']} layers, "
      f"{spec_before['parameters']:,} → {core.parameter_count():,} parameters")

# Inserting in the middle must not change anything either.
core.add_block(position=1)
with torch.no_grad():
    after_middle = core(codes)
check("a layer in the middle changes nothing too",
      torch.equal(before, after_middle))

# And the new block must be able to join in.
fresh = core.blocks[1]
with torch.no_grad():
    fresh.alpha1.fill_(0.1)
with torch.no_grad():
    after_waking = core(codes)
check("once the weighing factor leaves zero, the block joins in",
      not torch.equal(before, after_waking),
      "the block is not dead, it stands at zero and learns itself in")

print()

# --- 4. Repeatable ---------------------------------------------------------

print("--- Repeatable ---")
determinism.lock(4242)
c1 = network.Core(layers=2, width=64, heads=2, window=32)
determinism.lock(4242)
c2 = network.Core(layers=2, width=64, heads=2, window=32)
equal = all(torch.equal(a, b) for a, b in zip(c1.parameters(), c2.parameters()))
check("the same seed gives the same network", equal)

codes = torch.randint(0, 255, (1, 16))
c1.eval()
with torch.no_grad():
    check("the same input twice gives bit for bit the same output",
          torch.equal(c1(codes), c1(codes)))

# Backwards must be repeatable too, or the learning loop is not.
def gradient():
    determinism.lock(77)
    c = network.Core(layers=2, width=64, heads=2, window=32)
    determinism.begin_step(5)
    x = torch.randint(0, 255, (2, 16))
    c(x).square().mean().backward()
    return [p.grad.clone() for p in c.parameters()]

check("the backward pass is repeatable too",
      all(torch.equal(a, b) for a, b in zip(gradient(), gradient())),
      "attention written out by hand, exactly for this reason")

print()

# --- 5. The spec travels along ---------------------------------------------

print("--- The spec ---")
core = network.Core(layers=3, width=64, heads=2, window=32)
core.add_block()
rebuilt = network.Core.from_spec(core.spec())
check(
    "the same network can be rebuilt from the spec",
    rebuilt.spec()["layers"] == 4
    and rebuilt.parameter_count() == core.parameter_count(),
    "without the spec in the snapshot you no longer know after growth how "
    "many layers were in it",
)

print()

# --- 6. At true size -------------------------------------------------------

print("--- At true size ---")
big = network.Core()
s = big.spec()
print(f"         {s['layers']} layers, width {s['width']}, {s['heads']} heads, "
      f"window {s['window']}")
print(f"         {s['parameters']:,} parameters "
      f"({s['parameters'] * 16 / 1024**2:.0f} MB of weights, gradients and "
      f"optimizer state)")
check("the proposed size is what it should be",
      10_000_000 < s["parameters"] < 25_000_000)

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
