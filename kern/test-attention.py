"""
Tests the slimmer attention (16 Aug 2026) against the old one — bit for bit.

The old path divided the scores, built the causal ban in every block, and
let autograd run the backward of the in-place masks. The new path folds the
scale into q (in fp32 — under bf16 autocast it keeps dividing, see
network.py), keeps the ban, and does mask + softmax as one autograd node.
Faster on the P100 — but only worth anything if she computes exactly what
she computed before: the same output, the same gradients, the same weights
after learning, and the same answers with the cache. Both in fp32 and under
bf16 autocast (the trainer's mode), with and without activation
checkpointing.

The reference is the old forward, kept here verbatim. Anyone who changes
the attention has to keep this green — or say out loud that the rounding
changed and do it on a rungrens.

Run:  venv/bin/python kern/test-attention.py    (needs a card)
"""

import determinism                         # MUST come before torch
determinism.lock(1234)

import math
import sys

import torch

import learning
import network
import tasks
import tokens
import world
from network import Attention, _rotate

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
print("Test — the slimmer attention, bit for bit against the old one")
print("=" * 70)
print()

if not torch.cuda.is_available():
    print("no card — the comparison needs one; nothing tested")
    print(f"passed: {passed}    failed: {failed}")
    sys.exit(0)

DEVICE = "cuda"


# --- the old forward, verbatim (the reference) ------------------------------

def _old_forward(self, x, cos, sin, cache=None, key_mask=None):
    batch, length, width = x.shape
    qkv = self.to_qkv(x)
    q, k, v = qkv.chunk(3, dim=-1)
    shape = (batch, length, self.heads, self.head_size)
    q = q.view(shape).transpose(1, 2)
    k = k.view(shape).transpose(1, 2)
    v = v.view(shape).transpose(1, 2)

    q = _rotate(q, cos, sin)
    k = _rotate(k, cos, sin)

    if cache is not None:
        k, v = cache.append(k, v)
        del qkv

    device = x.device
    full_pass = q.shape[2] == k.shape[2]
    scores = (q @ k.transpose(-2, -1)) / math.sqrt(self.head_size)
    del q

    if full_pass:
        ban = torch.ones(length, length,
                         device=device, dtype=torch.bool).triu(1)
        scores.masked_fill_(ban, float("-inf"))
    if key_mask is not None:
        scores.masked_fill_(key_mask[:, None, None, :], float("-inf"))
        empty = torch.isinf(scores).all(dim=-1, keepdim=True)
        scores.masked_fill_(empty, 0.0)

    weight = torch.softmax(scores, dim=-1)
    del scores
    out = weight @ v
    del weight
    out = out.transpose(1, 2).reshape(batch, length, self.inner)
    return self.out(out), cache


_new_forward = Attention.forward


class old_attention:
    """Within this block every Attention runs the old forward."""

    def __enter__(self):
        Attention.forward = _old_forward

    def __exit__(self, *_):
        Attention.forward = _new_forward


def same(a, b):
    return a.shape == b.shape and a.dtype == b.dtype and torch.equal(a, b)


# --- 1. one core, one pass: output and gradients ----------------------------

LAYERS, WINDOW, BATCH, LENGTH = 4, 256, 6, 200


def open_gates(core):
    """The residual gates start at zero, so on a fresh core no gradient
    reaches the attention at all and any comparison there is empty. Open
    them: then the backward really runs through the branches."""
    with torch.no_grad():
        for name, p in core.named_parameters():
            if "alpha" in name:
                p.fill_(0.5)
    return core


def fresh_core(seed):
    determinism.begin_step(seed)
    return open_gates(network.Core(layers=LAYERS, window=WINDOW).to(DEVICE))


def one_pass(core, codes, bf16, backward=True):
    core.zero_grad(set_to_none=True)
    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=bf16):
        scores = core(codes)
        loss = torch.nn.functional.cross_entropy(
            scores[:, :-1].reshape(-1, tokens.VOCAB).float(),
            codes[:, 1:].reshape(-1))
    if backward:
        loss.backward()
        grads = [p.grad.detach().clone() for p in core.parameters()]
    else:
        grads = []
    return scores.detach().clone(), float(loss), grads


for bf16 in (False, True):
    label = "bf16 autocast" if bf16 else "fp32"
    core = fresh_core(7)
    determinism.begin_step(8)
    codes = torch.randint(0, tokens.VOCAB, (BATCH, LENGTH), device=DEVICE)
    with old_attention():
        s_old, l_old, g_old = one_pass(core, codes, bf16)
    s_new, l_new, g_new = one_pass(core, codes, bf16)
    check(f"{label}: the scores of a full pass are bit for bit the same",
          same(s_old, s_new), f"max |diff| {(s_old.float() - s_new.float()).abs().max():.3e}")
    check(f"{label}: the loss is the same", l_old == l_new, f"{l_old} vs {l_new}")
    check(f"{label}: every gradient is bit for bit the same",
          len(g_old) == len(g_new) and all(same(a, b) for a, b in zip(g_old, g_new)),
          f"{sum(0 if same(a, b) else 1 for a, b in zip(g_old, g_new))} of {len(g_old)} differ")

# --- 2. the ban is cached, and it is the right one --------------------------

network._BAN.clear()
c1 = network._causal_ban(37, torch.device(DEVICE))
c2 = network._causal_ban(37, torch.device(DEVICE))
check("the causal ban is built once per length and reused", c1 is c2)
check("and it bans exactly the future",
      torch.equal(c1, torch.ones(37, 37, device=DEVICE, dtype=torch.bool).triu(1)))
check("the scale folds into q at head size 64 (root 8, a power of two)",
      Attention(384, 6)._scale_folds and Attention(384, 6)._scale == 0.125)
check("… and not at a head size whose root is no power of two",
      not Attention(360, 6, head_size=60)._scale_folds)

# --- 3. learning: weights after steps, fp32 and bf16, with checkpointing ---

world.MAX_DEPTH = max(world.MAX_DEPTH, 6)
STOF = world.learning_tasks("rekenen", 4, 24, start=5000, room=WINDOW - 112)


def learn_a_bit(seed, bf16, checkpointing):
    determinism.begin_step(seed)
    core = network.Core(layers=LAYERS, window=WINDOW)
    L = learning.Learner(core=core, device=DEVICE, batch_size=8,
                         replay_share=0.0, bf16=bf16,
                         checkpointing=checkpointing)
    for i in range(3):
        determinism.begin_step(seed + 1 + i)
        L.learn(STOF[8 * i:8 * i + 8], remember=False)
    return [p.detach().clone() for p in L.core.parameters()]


for bf16 in (False, True):
    for ckpt in (False, True):
        label = ("bf16" if bf16 else "fp32") + (" + checkpointing" if ckpt else "")
        with old_attention():
            w_old = learn_a_bit(11, bf16, ckpt)
        w_new = learn_a_bit(11, bf16, ckpt)
        check(f"{label}: weights after three learning steps are bit for bit the same",
              all(same(a, b) for a, b in zip(w_old, w_new)),
              f"{sum(0 if same(a, b) else 1 for a, b in zip(w_old, w_new))} of {len(w_old)} differ")

# --- 4. answering: the cache path with left padding ------------------------

determinism.begin_step(21)
core = network.Core(layers=LAYERS, window=WINDOW)
L = learning.Learner(core=core, device=DEVICE, batch_size=8,
                     replay_share=0.0, bf16=False)
vragen = [tasks.make("rekenen", g, n) for g in (1, 2, 3) for n in (0, 1)]
with old_attention():
    determinism.begin_step(22)
    a_old = L.answer(vragen, at_most=40)
determinism.begin_step(22)
a_new = L.answer(vragen, at_most=40)
check("answers through the cache (left padding, key mask) are identical",
      a_old == a_new, f"{a_old[:2]} vs {a_new[:2]}")

# the same in bf16, as the trainer answers
L2 = learning.Learner(core=core, device=DEVICE, batch_size=8,
                      replay_share=0.0, bf16=True)
with old_attention():
    determinism.begin_step(23)
    b_old = L2.answer(vragen, at_most=40)
determinism.begin_step(23)
b_new = L2.answer(vragen, at_most=40)
check("… and identical under bf16 autocast", b_old == b_new)

# --- 5. a grown net (more heads than the width holds) takes the same road --

determinism.begin_step(31)
core = open_gates(network.Core(layers=2, window=128).to(DEVICE))
core.grow_heads(2)                       # 6 → 8 heads, inner 512 > width 384
with torch.no_grad():                    # give the new heads something to say
    for block in core.blocks:
        block.attention.out.weight.add_(0.01)
codes = torch.randint(0, tokens.VOCAB, (3, 100), device=DEVICE)
with old_attention():
    s_old, _, g_old = one_pass(core, codes, False)
s_new, _, g_new = one_pass(core, codes, False)
check("a net grown wider computes the same scores and gradients",
      same(s_old, s_new) and all(same(a, b) for a, b in zip(g_old, g_new)))

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
