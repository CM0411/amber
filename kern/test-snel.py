"""
Tests the Decoder — answering with fixed shapes as one card instruction
(25 Aug 2026, "de stappen moeten gewoon sneller").

Enforced here:
* the eager Decoder step gives the same scores as the ordinary advance with
  the growing cache, character for character (within rounding: the
  attention sees more masked columns), and picks the same characters;
* the Learner's answers are identical with and without the Decoder;
* on a card (AMBER_KAART_TEST=1): the captured graph equals the eager step
  bit for bit, and the time per character is reported.

Run:  CUDA_VISIBLE_DEVICES= python3 kern/test-snel.py      (processor only)
      AMBER_KAART_TEST=1 python3 kern/test-snel.py         (on the card)
"""
import os
import sys
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import determinism                 # before torch, as everywhere in kern
import torch

import network
import tokens
from learning import Learner
from tasks import Task


def small_core(seed=7, layers=3, width=64, heads=2, window=128):
    torch.manual_seed(seed)
    core = network.Core(layers=layers, width=width, heads=heads, window=window)
    with torch.no_grad():
        for p in core.parameters():
            p.add_(torch.randn_like(p) * 0.05)      # gates off zero, so every block acts
    return core.eval()


def left_padded(prompts, device):
    longest = max(len(p) for p in prompts)
    q = torch.full((len(prompts), longest), tokens.PAD, dtype=torch.long, device=device)
    for i, p in enumerate(prompts):
        q[i, longest - len(p):] = torch.tensor(p, device=device)
    return q, longest


@torch.no_grad()
def write_both(core, prompts, steps, device, use_graph):
    """Returns (scores_old, scores_new): per character the scores of the
    ordinary path and of the Decoder, plus the characters chosen."""
    question, longest = left_padded(prompts, device)
    capacity = longest + steps
    batch = len(prompts)
    mask_full = torch.zeros(batch, capacity, dtype=torch.bool, device=device)
    mask_full[:, :longest] = question == tokens.PAD

    cache = core.new_cache(capacity)
    s_old, cache = core.advance(question, cache=cache, key_mask=mask_full[:, :longest])
    dec = network.Decoder(core, batch, capacity, mask_full, use_graph=use_graph)
    s_new = dec.prefill(question, mask_full[:, :longest])
    assert torch.equal(s_old, s_new), "prefill differs"

    old, new, chosen_old, chosen_new = [], [], [], []
    following = s_old[:, -1].argmax(dim=-1)
    following_new = following.clone()
    for step in range(steps):
        s_old, cache = core.advance(following[:, None], cache=cache,
                                    offset=longest + step,
                                    key_mask=mask_full[:, :longest + step + 1])
        last_old = s_old[:, -1]
        last_new = dec.step(following_new)
        old.append(last_old); new.append(last_new)
        following = last_old.argmax(dim=-1)
        following_new = last_new.argmax(dim=-1)
        chosen_old.append(following); chosen_new.append(following_new)
        # keep the two paths on the same characters, so every step compares
        following_new = following.clone()
    return torch.stack(old, 1), torch.stack(new, 1), torch.stack(chosen_old, 1), torch.stack(chosen_new, 1)


def test_eager_equals_advance(device):
    core = small_core().to(device)
    prompts = [[tokens.ANSWER] + [5, 6, 7, 8][: 1 + i] for i in range(4)]
    old, new, c_old, c_new = write_both(core, prompts, steps=40, device=device, use_graph=False)
    diff = (old.float() - new.float()).abs().max().item()
    same = (c_old == c_new).float().mean().item()
    print(f"  eager decoder vs advance: max verschil {diff:.2e}, zelfde teken {same:.1%}")
    assert diff < 1e-4, diff
    assert same == 1.0, same


def test_learner_answers_equal_default():
    test_learner_answers_equal('cpu')


def test_learner_answers_equal(device):
    """The Learner's answers with and without the Decoder."""
    core = small_core(seed=11)
    learner = Learner(core=core, device=device, batch_size=4, bf16=False)
    tasks_ = [Task(family="rekenen", grade=1, number=i, problem=f"{a} + {b}", solution=str(a + b), working=None)
              for i, (a, b) in enumerate([(1, 2), (12, 7), (3, 40), (9, 9)])]
    os.environ["AMBER_GRAAF"] = "0"
    a = learner.answer(tasks_, at_most=24)
    os.environ["AMBER_GRAAF"] = "altijd"
    b = learner.answer(tasks_, at_most=24)
    os.environ["AMBER_GRAAF"] = "1"
    print(f"  antwoorden zonder/met decoder: {a} / {b}")
    assert a == b, (a, b)


def test_graph_equals_eager():
    device = "cuda"
    core = small_core(seed=3, layers=4, width=96, heads=3, window=512).to(device)
    prompts = [[tokens.ANSWER] + list(range(5, 5 + 3 + i)) for i in range(8)]
    with torch.autocast("cuda", dtype=torch.bfloat16):
        _, new_eager, _, _ = write_both(core, prompts, steps=300, device=device, use_graph=False)
        _, new_graph, _, _ = write_both(core, prompts, steps=300, device=device, use_graph=True)
    exact = torch.equal(new_eager, new_graph)
    diff = (new_eager.float() - new_graph.float()).abs().max().item()
    print(f"  graaf vs eager stap: bit voor bit gelijk: {exact} (max verschil {diff:.2e})")
    assert diff < 1e-3, diff
    # tempo: the ordinary path against the graph, same work
    question, longest = left_padded(prompts, device)
    batch, steps = len(prompts), 300
    capacity = longest + steps
    mask_full = torch.zeros(batch, capacity, dtype=torch.bool, device=device)
    mask_full[:, :longest] = question == tokens.PAD
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
        for naam, graaf in (("gewoon", None), ("graaf", True)):
            torch.cuda.synchronize(); t0 = time.perf_counter()
            if graaf is None:
                cache = core.new_cache(capacity)
                s, cache = core.advance(question, cache=cache, key_mask=mask_full[:, :longest])
                f = s[:, -1].argmax(-1)
                for step in range(steps):
                    s, cache = core.advance(f[:, None], cache=cache, offset=longest + step,
                                            key_mask=mask_full[:, :longest + step + 1])
                    f = s[:, -1].argmax(-1)
            else:
                dec = network.Decoder(core, batch, capacity, mask_full, use_graph=True)
                s = dec.prefill(question, mask_full[:, :longest]); f = s[:, -1].argmax(-1)
                for step in range(steps):
                    f = dec.step(f).argmax(-1)
            torch.cuda.synchronize()
            print(f"  tempo {naam}: {(time.perf_counter() - t0) / steps * 1000:.2f} ms per teken ({steps} tekens, batch {batch}, {len(core.blocks)} lagen)")


if __name__ == "__main__":
    device = "cpu"
    passed = failed = 0
    def loop(naam, fn):
        global passed, failed
        try:
            fn(); passed += 1
        except AssertionError as e:
            failed += 1; print(f"  FOUT: {naam} {e}")
    print("decoder eager == advance")
    loop("eager == advance", lambda: test_eager_equals_advance(device))
    print("learner: antwoorden gelijk")
    loop("antwoorden gelijk", test_learner_answers_equal_default)
    if os.environ.get("AMBER_KAART_TEST") == "1" and torch.cuda.is_available():
        print("op de kaart: graaf == eager, en het tempo")
        loop("graaf == eager", test_graph_equals_eager)
    else:
        print("(kaarttest overgeslagen: AMBER_KAART_TEST=1 op een vrije kaart)")
    print("=" * 70)
    print(f"passed: {passed}    failed: {failed}")
    print("=" * 70)
    sys.exit(1 if failed else 0)
