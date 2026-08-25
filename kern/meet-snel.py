"""
Measures the Decoder at the run's real shape on a free card (25 Aug 2026):
time per character and peak card memory, ordinary path against the graph.

Run:  python3 kern/meet-snel.py            (defaults: run 7.3's shape)
      python3 kern/meet-snel.py 64 1400    (batch, capacity)
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import determinism                 # before torch
import torch

import network
import tokens
from learning import bf16_usable

batch = int(sys.argv[1]) if len(sys.argv) > 1 else 64
capacity = int(sys.argv[2]) if len(sys.argv) > 2 else 1400
question_len = 200
steps = capacity - question_len
device = "cuda"
torch.manual_seed(1)
core = network.Core(layers=20, width=384, heads=6, hidden=1536, window=2048).to(device).eval()
with torch.no_grad():
    for p in core.parameters():
        p.add_(torch.randn_like(p) * 0.02)
bf16 = bf16_usable(device)
print(f"kaart {torch.cuda.get_device_name(0)}, torch {torch.__version__}, bf16 {bf16}, batch {batch}, ruimte {capacity}, {steps} tekens")

prompts = [[tokens.ANSWER] + [(7 * i + j) % 90 + 10 for j in range(question_len - 1 - (i % 5))] for i in range(batch)]
longest = max(len(p) for p in prompts)
question = torch.full((batch, longest), tokens.PAD, dtype=torch.long, device=device)
for i, p in enumerate(prompts):
    question[i, longest - len(p):] = torch.tensor(p, device=device)
mask_full = torch.zeros(batch, capacity, dtype=torch.bool, device=device)
mask_full[:, :longest] = question == tokens.PAD

# fp16 where bf16 is not native (the P100): lighter kernels, closer to the
# launch-bound regime of the Z490's card
soort = torch.bfloat16 if bf16 else torch.float16
halve = bf16 or os.environ.get("AMBER_MEET_FP16", "1") == "1"
print(f"  rekenen in {'fp32' if not halve else str(soort).split('.')[-1]} (autocast)")
uit = {}
cache = dec = s = None
for naam in ("gewoon", "graaf"):
    del cache, dec, s                         # nothing of the previous run may stay on the card
    cache = dec = s = None
    torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats(); torch.cuda.synchronize()
    t0 = time.perf_counter()
    with torch.no_grad(), torch.autocast("cuda", dtype=soort, enabled=halve):
        if naam == "gewoon":
            cache = core.new_cache(capacity)
            s, cache = core.advance(question, cache=cache, key_mask=mask_full[:, :longest])
            f = s[:, -1].argmax(-1); gekozen = [f]
            for step in range(steps):
                s, cache = core.advance(f[:, None], cache=cache, offset=longest + step,
                                        key_mask=mask_full[:, :longest + step + 1])
                f = s[:, -1].argmax(-1); gekozen.append(f)
        else:
            dec = network.Decoder(core, batch, capacity, mask_full, use_graph=True)
            s = dec.prefill(question, mask_full[:, :longest])
            f = s[:, -1].argmax(-1); gekozen = [f]
            for step in range(steps):
                f = dec.step(f).argmax(-1); gekozen.append(f)
    torch.cuda.synchronize()
    dt = time.perf_counter() - t0
    piek = torch.cuda.max_memory_allocated() / 2**20
    uit[naam] = torch.stack(gekozen, 1)
    print(f"  {naam:7s}: {dt / steps * 1000:6.2f} ms per teken, {dt:5.1f} s totaal, piek {piek:.0f} MiB")
zelfde = (uit["gewoon"] == uit["graaf"]).float().mean().item()
print(f"  zelfde tekens gekozen: {zelfde:.2%}  (rondingen mogen af en toe een ander teken geven bij een gelijkspel)")
