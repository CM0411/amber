"""Leerpad-proef: waar zit de piek bij leren mét checkpointing, en wat
verschuift hem — chunk-budget, eerste vs tweede stap, bf16-autocast.

Tijdelijk meetscript (15 aug 2026), vorm van run 6. Draai op één kaart:
  CUDA_VISIBLE_DEVICES=1 venv/bin/python fase1/vram-leerpad-proef.py
"""
import sys, time
sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinism
determinism.lock(31415)
import torch
import torch.nn.functional as F
import learning, network, world, tokens

MB = 1024 ** 2
LAGEN, VENSTER, PARTIJ, DIEPTE = 12, 1536, 64, 60
BF16 = "--bf16" in sys.argv

world.MAX_DEPTH = max(world.MAX_DEPTH, DIEPTE)
stof = world.learning_tasks("rekenen", DIEPTE, PARTIJ, room=VENSTER - 112)


def bouw():
    determinism.begin_step(1)
    core = network.Core(layers=LAGEN, window=VENSTER)
    return learning.Learner(core=core, device="cuda", batch_size=PARTIJ,
                            replay_share=0.0, bf16=BF16, checkpointing=True)


def piek():
    torch.cuda.synchronize()
    return torch.cuda.max_memory_allocated() / MB


def reset():
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()


def stap_gefaseerd(L, budget):
    """Kopie van _step_real met meetpunten; zelfde getallen."""
    L.core.train()
    codes, mask = L._make_batch(stof)
    n, length = codes.shape
    chunk_size = max(1, min(n, budget // max(1, length * length)))
    L.optimizer.zero_grad(set_to_none=True)
    total_counts = int(mask[:, 1:].sum())
    fw = bw = 0.0
    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=L.bf16):
        for i in range(0, n, chunk_size):
            c = codes[i:i + chunk_size]
            m = mask[i:i + chunk_size]
            reset()
            scores = L._compute_core(c)
            predicted = scores[:, :-1].reshape(-1, tokens.VOCAB)
            target = c[:, 1:].reshape(-1)
            counts = m[:, 1:].reshape(-1)
            summed = F.cross_entropy(predicted[counts], target[counts],
                                     reduction="sum")
            loss = summed / max(1, total_counts)
            fw = max(fw, piek())
            reset()
            loss.backward()
            bw = max(bw, piek())
    reset()
    torch.nn.utils.clip_grad_norm_(L.core.parameters(), 1.0)
    L.optimizer.step()
    L.steps += 1
    opt = piek()
    return chunk_size, length, fw, bw, opt


print(f"vorm: {LAGEN} lagen, venster {VENSTER}, partij {PARTIJ}, rekenen "
      f"{DIEPTE}, {'bf16-autocast' if BF16 else 'fp32'}")

referentie = None
for budget in (10_000_000, 8_000_000, 6_000_000, 4_000_000, 2_000_000):
    learning._CHUNK_BUDGET = budget
    torch.cuda.empty_cache()
    L = bouw()
    rust = torch.cuda.memory_allocated() / MB
    # stap 1 zoals vram-meting: nog geen optimizer-toestand tijdens backward
    determinism.begin_step(2)
    reset()
    t0 = time.time()
    L.learn(stof)
    torch.cuda.synchronize()
    t1 = time.time() - t0
    p1 = piek()
    na1 = torch.cuda.memory_allocated() / MB
    # gewichten na stap 1 voor de bitvergelijking tussen budgetten
    staat = {k: v.detach().cpu().clone() for k, v in L.core.state_dict().items()}
    if referentie is None:
        referentie = staat
        gelijk = "referentie"
    else:
        anders = sum(int((referentie[k] != staat[k]).sum()) for k in staat)
        totaal = sum(v.numel() for v in staat.values())
        maxd = max(float((referentie[k].float() - staat[k].float()).abs().max())
                   for k in staat)
        gelijk = (f"{anders} van {totaal} gewichten anders dan bij 10M "
                  f"(max |verschil| {maxd:.2e})")
    # stap 2: nu bestaat de optimizer-toestand wél
    determinism.begin_step(3)
    reset()
    t0 = time.time()
    L.learn(stof)
    torch.cuda.synchronize()
    t2 = time.time() - t0
    p2 = piek()
    # stap 3 gefaseerd
    determinism.begin_step(4)
    chunk, length, fw, bw, opt = stap_gefaseerd(L, budget)
    print(f"\nbudget {budget/1e6:.0f}M -> chunk {chunk} (lengte {length}), "
          f"rust {rust:.0f} MB")
    print(f"  stap 1: piek {p1:.0f} MB, {t1:.1f} s; daarna resident {na1:.0f} MB")
    print(f"  stap 2: piek {p2:.0f} MB, {t2:.1f} s   (+{p2-p1:.0f} MB t.o.v. stap 1)")
    print(f"  fasen : voorwaarts {fw:.0f} | achterwaarts {bw:.0f} | "
          f"optimizer {opt:.0f} MB")
    print(f"  bits  : {gelijk}")
    del L
    torch.cuda.empty_cache()
