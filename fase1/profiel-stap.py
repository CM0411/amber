"""Waar gaat de tijd heen in één leerstap? (16 aug 2026, P100)

Zelfde opzet als tempo-p100.py, maar met torch.profiler over één stap
na opwarmen. Toont de zwaarste CUDA-kernels en de tijd per fase.

  CUDA_VISIBLE_DEVICES=1 venv/bin/python fase1/profiel-stap.py --lagen 12 --venster 1536
"""
import argparse, sys, time
sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinism
determinism.lock(27182)
import torch
from torch.profiler import profile, ProfilerActivity
import learning, network, world

p = argparse.ArgumentParser()
p.add_argument("--lagen", type=int, default=12)
p.add_argument("--venster", type=int, default=1536)
p.add_argument("--partij", type=int, default=64)
p.add_argument("--diepte", type=int, default=60)
p.add_argument("--checkpointing", action="store_true")
p.add_argument("--rijen", type=int, default=25)
a = p.parse_args()

world.MAX_DEPTH = max(world.MAX_DEPTH, a.diepte)
determinism.begin_step(1)
core = network.Core(layers=a.lagen, window=a.venster)
L = learning.Learner(core=core, device="cuda", batch_size=a.partij,
                     replay_share=0.0, bf16=False, checkpointing=a.checkpointing)
partijen = [world.learning_tasks("rekenen", a.diepte, a.partij, start=1000 * k,
                                 room=a.venster - 112) for k in range(4)]
for k in range(3):
    determinism.begin_step(2 + k)
    L.learn(partijen[k])
torch.cuda.synchronize()

# --- fasen met de hand: partij bouwen, voorwaarts+achterwaarts, optimizer
codes, mask = L._make_batch(partijen[3])
n, length = codes.shape
print(f"partij {n} × {length}, chunk {max(1, min(n, learning._CHUNK_BUDGET // (length*length)))}")

determinism.begin_step(10)
with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA]) as prof:
    t0 = time.perf_counter()
    L.learn(partijen[3])
    torch.cuda.synchronize()
    print(f"stap: {(time.perf_counter() - t0) * 1000:.0f} ms")
print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=a.rijen,
                                max_name_column_width=60))
