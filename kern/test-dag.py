"""
Tests her day (25 Aug 2026, Cley: a real answer to "hoe was je dag").

Enforced here:
* the tally follows work(): practised, played, self-test marks, gates;
* dag_lessen() speaks her idiom, deterministic, with "hoe was je dag?";
* dag_afsluiten() puts the lessons in the memory and starts a fresh day;
* the tally travels in carry()/restore().

Run:  CUDA_VISIBLE_DEVICES= python3 kern/test-dag.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import determinism                 # before torch
determinism.lock(2)
import torch

import network
from learning import Learner, dag_lessen, SPEL_DUUR

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        print(f"  FOUT: {name} {detail}")


# --- dag_lessen from a hand-made tally ---------------------------------
dag = {"geoefend": {"rekenen": 5, "taal": 3, "code": 2, "puzzel": 1}, "gespeeld": {"puzzel": 2},
       "scores": {"rekenen": (2.8, 3), "taal": (0.4, 2)}, "open": ["code"]}
l = dict(dag_lessen(dag, 3))
check("wat oefende je", l.get("dag 3: wat oefende je?") == "ik oefende rekenen, taal en code", str(l))
check("wat gaat goed", l.get("dag 3: wat gaat goed?") == "rekenen gaat goed")
check("wat is moeilijk", l.get("dag 3: wat is moeilijk?") == "taal is moeilijk")
check("wat speelde je", l.get("dag 3: wat speelde je?") == "ik speelde puzzel")
check("wat ging open", l.get("dag 3: wat ging open?") == "ik mag dieper in code")
check("hoe was je dag (genummerd)", l.get("dag 3: hoe was je dag?") == "ik oefende rekenen, taal en code ; rekenen gaat goed ; taal is moeilijk")
check("hoe was je dag (kaal)", l.get("hoe was je dag?") == l.get("dag 3: hoe was je dag?"))
check("lege dag: niets", dag_lessen({"geoefend": {}, "gespeeld": {}, "scores": {}, "open": []}, 1) == [])
check("deterministisch", dag_lessen(dag, 3) == dag_lessen(dag, 3))

# --- the tally follows work() -------------------------------------------
torch.manual_seed(5)
core = network.Core(layers=2, width=32, heads=2, window=256)
L = Learner(core=core, device="cpu", batch_size=4, bf16=False, probe_every=1)
r_spel = L.work(2)                                   # play hour
r_gewoon = L.work(SPEL_DUUR + 4)                     # measured
d = L.dag
check("gespeeld geteld", d["gespeeld"].get(r_spel["family"], 0) == 1, str(d))
check("geoefend geteld", d["geoefend"].get(r_gewoon["family"], 0) == 1, str(d))
check("cijfer geteld", r_gewoon["family"] in d["scores"] and d["scores"][r_gewoon["family"]][1] == 1)
voor = len(L.memory)
lessen = L.dag_afsluiten(SPEL_DUUR + 4)
check("lessen bij het afsluiten", len(lessen) >= 4, str(lessen))
check("lessen in het geheugen", len(L.memory) == voor + len(lessen), f"{voor} -> {len(L.memory)}")
check("nieuwe dag leeg", L.dag == {"geoefend": {}, "gespeeld": {}, "scores": {}, "open": []})
check("kaal 'hoe was je dag?' erbij", any(q == "hoe was je dag?" for q, _ in lessen))

# --- carry / restore ----------------------------------------------------
L.work(SPEL_DUUR + 8)
gedragen = L.carry()
check("dag reist mee", "dag" in gedragen and gedragen["dag"]["geoefend"])
L2 = Learner(core=network.Core(layers=2, width=32, heads=2, window=256), device="cpu", batch_size=4, bf16=False)
L2.restore(gedragen, step=SPEL_DUUR + 8)
check("dag terug na restore", L2.dag == L.dag, f"{L2.dag} != {L.dag}")
L3 = Learner(core=network.Core(layers=2, width=32, heads=2, window=256), device="cpu", batch_size=4, bf16=False)
oud = dict(gedragen); oud.pop("dag")
L3.restore(oud, step=1)
check("oude momentopname zonder dag: verse dag", L3.dag == {"geoefend": {}, "gespeeld": {}, "scores": {}, "open": []})

print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(1 if failed else 0)
