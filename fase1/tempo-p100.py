"""Tempometing — hoe snel leert ze op de P100's, in een gegeven vorm?

Op Cleys vraag (16 aug 2026): de Z490 (3070 Ti, 8 GB) is straks te klein
en dan verhuist de training naar de P100's. Wat kost een leerstap daar,
en welke knoppen doen ertoe? Dit script bouwt een Learner in de gevraagde
vorm, doet een paar opwarmstappen en meet daarna het gemiddelde over
`--stappen` echte leerstappen (partij 64, stof rekenen op de gevraagde
diepte, herhaling 0 — dus zuiver het rekenwerk). Ook de piek-VRAM.

Welke kaarten meedoen bepaal je buiten het script:

  CUDA_VISIBLE_DEVICES=0,1 venv/bin/python fase1/tempo-p100.py --lagen 12 --venster 1536
  venv/bin/torchrun --standalone --nproc_per_node=2 fase1/tempo-p100.py ...   (DDP: twee processen)
  CUDA_VISIBLE_DEVICES=1   venv/bin/python fase1/tempo-p100.py ... --checkpointing
  ...                                                           --fused   (AdamW fused-kernel)
"""
import argparse, sys, time
sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinism
determinism.lock(27182)
import torch
import learning, network, parallel, world
parallel.start()                    # onder torchrun: één proces per kaart
say = print if parallel.chief() else (lambda *a, **k: None)

p = argparse.ArgumentParser()
p.add_argument("--lagen", type=int, default=12)
p.add_argument("--venster", type=int, default=1536)
p.add_argument("--partij", type=int, default=64)
p.add_argument("--diepte", type=int, default=60)
p.add_argument("--stappen", type=int, default=10)
p.add_argument("--checkpointing", action="store_true")
p.add_argument("--bf16", action="store_true")
p.add_argument("--fused", action="store_true", help="AdamW met fused=True")
p.add_argument("--koppen", type=int, default=6)
p.add_argument("--verborgen", type=int, default=None)
p.add_argument("--chunkbudget", type=int, default=None,
               help="learning._CHUNK_BUDGET (partij × lengte² per doorgang; standaard 10 M)")
a = p.parse_args()
if a.chunkbudget:
    learning._CHUNK_BUDGET = a.chunkbudget

MB = 1024 ** 2
world.MAX_DEPTH = max(world.MAX_DEPTH, a.diepte)
kaarten = torch.cuda.device_count()
determinism.begin_step(1)
core = network.Core(layers=a.lagen, window=a.venster, heads=a.koppen,
                    hidden=a.verborgen)
L = learning.Learner(core=core, device="cuda", batch_size=a.partij,
                     replay_share=0.0, bf16=a.bf16, checkpointing=a.checkpointing)
if a.fused:
    oud = L.optimizer.param_groups[0]
    L.optimizer = torch.optim.AdamW(L.core.parameters(), lr=oud["lr"],
                                    weight_decay=oud["weight_decay"], fused=True)
say(f"vorm: {a.lagen} lagen × {core.width}, {core.heads} koppen, {core.hidden} "
      f"verborgen, venster {a.venster}, partij {a.partij}, "
      f"{L.core.parameter_count() / 1e6:.1f} M parameters · "
      f"{f'{parallel.world()} processen (DDP)' if parallel.active() else f'{kaarten} kaart(en)'} · "
      f"{'bf16' if a.bf16 else 'fp32'} · checkpointing {'aan' if a.checkpointing else 'uit'}"
      f"{' · fused AdamW' if a.fused else ''} · chunkbudget {learning._CHUNK_BUDGET / 1e6:.0f} M",
      flush=True)
lengte = max(len(t.problem) + len(t.to_learn()) + 3 for t in
             world.learning_tasks("rekenen", a.diepte, a.partij, start=3000, room=a.venster - 112))
say(f"langste reeks ~{lengte} tekens → doorgangen van "
      f"{max(1, min(a.partij, learning._CHUNK_BUDGET // (lengte * lengte)))} reeksen", flush=True)

# elke stap een andere partij, zoals in het echt
partijen = [world.learning_tasks("rekenen", a.diepte, a.partij,
                                 start=1000 * k, room=a.venster - 112)
            for k in range(3 + a.stappen)]

torch.cuda.reset_peak_memory_stats()
for k in range(3):                                   # opwarmen
    determinism.begin_step(2 + k)
    L.learn(partijen[k])
torch.cuda.synchronize()
t0 = time.perf_counter()
for k in range(a.stappen):
    determinism.begin_step(10 + k)
    L.learn(partijen[3 + k])
torch.cuda.synchronize()
per = (time.perf_counter() - t0) / a.stappen
if parallel.active():          # elk proces zijn eigen kaart; de drukste telt
    _, pieken = parallel.same(torch.cuda.max_memory_allocated(torch.cuda.current_device()))
    piek = max(pieken) / MB
else:
    piek = max(torch.cuda.max_memory_allocated(i) for i in range(kaarten)) / MB
say(f"{per * 1000:.0f} ms/stap · {a.partij / per:.0f} taken/s · piek {piek:.0f} MB "
      f"op de drukste kaart", flush=True)
parallel.stop()
