"""VRAM-meting — waar gaat het geheugen heen, per fase, bij een gegeven vorm?

Op Cleys vraag (15 aug 2026): het VRAM optimaliseren zonder
kwaliteitsverlies. Eerst meten, dan pas draaien aan knoppen. Dit script
bouwt een Learner in de gevraagde vorm (lagen, venster, partij), doet
één echte leerstap en één echte antwoordronde op stof van de gevraagde
diepte, en meet per fase de piek (`torch.cuda.max_memory_allocated`),
met en zonder checkpointing. Daarnaast rekent het de vaste posten uit:
gewichten + gradiënten + optimizer (16 bytes per parameter in fp32) en
de KV-cache bij het antwoorden.

Op de P100 is alles fp32; de 3070 Ti rekent onder autocast in bf16, dus
activaties en cache zijn daar ruwweg de helft. Draai op één kaart:

  CUDA_VISIBLE_DEVICES=1 venv/bin/python fase1/vram-meting.py \\
      --lagen 12 --venster 1536 --partij 64 --diepte 60
"""
import argparse
import sys

sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinism
determinism.lock(31415)
import torch
import exams, learning, network, world

p = argparse.ArgumentParser()
p.add_argument("--lagen", type=int, default=8)
p.add_argument("--venster", type=int, default=1024)
p.add_argument("--partij", type=int, default=64)
p.add_argument("--diepte", type=int, default=38,
               help="rekenen-diepte van de stof (bepaalt de lengte)")
p.add_argument("--bf16", action="store_true", help="autocast bf16 (Z490)")
a = p.parse_args()

MB = 1024 ** 2
world.MAX_DEPTH = max(world.MAX_DEPTH, a.diepte)
stof = world.learning_tasks("rekenen", a.diepte, a.partij, room=a.venster - 112)
langste = max(len(t.problem) + len(t.to_learn()) + 3 for t in stof)
print(f"vorm: {a.lagen} lagen, venster {a.venster}, partij {a.partij}, "
      f"stof rekenen {a.diepte} (langste reeks {langste} tekens), "
      f"{'bf16' if a.bf16 else 'fp32'}")


def bouw(flag):
    determinism.begin_step(1)
    core = network.Core(layers=a.lagen, window=a.venster)
    L = learning.Learner(core=core, device="cuda", batch_size=a.partij,
                         replay_share=0.0, bf16=a.bf16, checkpointing=flag)
    return L


def piek():
    torch.cuda.synchronize()
    return torch.cuda.max_memory_allocated() / MB


def reset():
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()


uitkomst = {}
for flag in (False, True):
    reset()
    try:
        L = bouw(flag)
        params = L.core.parameter_count()
        rust = torch.cuda.memory_allocated() / MB
        # --- leren: de TWEEDE stap telt (de eerste heeft nog geen
        # optimizertoestand en meet 165 MB te laag — vondst van 15 aug)
        determinism.begin_step(2)
        L.learn(stof)
        reset()
        determinism.begin_step(4)
        L.learn(stof)
        leren = piek()
        # --- antwoorden (één ronde, ruimte zoals de leerlus geeft)
        reset()
        determinism.begin_step(3)
        ruimte = learning.room_for(a.diepte, "rekenen", a.venster)
        L.answer(stof, at_most=ruimte)
        antwoorden = piek()
        # --- het proefwerk: per blad per familie tot 150 rijen tegelijk —
        # bij stapel/code 84 rijen: dát is de echte antwoordpiek, niet de
        # poging van 64 (vondst van 15 aug; ~450 MB hoger)
        reset()
        determinism.begin_step(5)
        exams.take(L, at_most=150)
        proefwerk = piek()
        gereserveerd = torch.cuda.max_memory_reserved() / MB
        uitkomst[flag] = (rust, leren, antwoorden, ruimte, params, proefwerk,
                          gereserveerd)
        del L
    except torch.cuda.OutOfMemoryError:
        uitkomst[flag] = None
        print(f"checkpointing={flag}: PAST NIET op deze kaart "
              f"({torch.cuda.get_device_properties(0).total_memory / MB:.0f} MB)")
    torch.cuda.empty_cache()

for flag, u in uitkomst.items():
    if u is None:
        continue
    rust, leren, antwoorden, ruimte, params, proefwerk, gereserveerd = u
    print(f"\ncheckpointing {'aan' if flag else 'uit'}:")
    print(f"  gewichten+optimizer in rust : {rust:>7.0f} MB  "
          f"({params:,} parameters × 16 B = {params * 16 / MB:.0f} MB "
          f"na de eerste stap)".replace(",", "."))
    print(f"  piek bij leren               : {leren:>7.0f} MB")
    print(f"  piek bij antwoorden (poging) : {antwoorden:>7.0f} MB  "
          f"(schrijfruimte {ruimte})")
    print(f"  piek bij proefwerk (150/blad): {proefwerk:>7.0f} MB  "
          f"(gereserveerd door de allocator {gereserveerd:.0f} MB — dát ziet "
          f"nvidia-smi)")

# de KV-cache bij het antwoorden, uitgerekend — met de lengte van de vráág
# (links gepad tot de langste vraag) plus de schrijfruimte, niet de leerreeks
import tokens
u = uitkomst.get(False) or uitkomst.get(True)
if u:
    ruimte, params = u[3], u[4]
    langste_vraag = max(len(tokens.question_to_sequence(t)) for t in stof)
    lengte = min(a.venster, langste_vraag + ruimte)
    bytes_per = 2 if a.bf16 else 4
    kv = a.partij * a.lagen * 2 * lengte * 384 * bytes_per / MB
    print(f"\nKV-cache bij antwoorden (uitgerekend): partij {a.partij} × "
          f"{a.lagen} lagen × 2 × {lengte} posities × 384 × {bytes_per} B "
          f"= {kv:.0f} MB")
    print(f"vaste post: {params * 16 / MB:.0f} MB (gewichten, gradiënten, "
          f"twee Adam-momenten; blijft fp32 — dat is de kwaliteit)")
