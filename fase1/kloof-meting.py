"""De CPU-kloof meten — waar gaat de tijd van één stap heen?

Op 15 aug 2026 zakte de GPU-benutting van run 5 tussen de stappen naar
40–50% terwijl de trainer op één CPU-kern op 98% zat. Dit script laat de
leerder een reeks stappen zetten precies zoals `life.py` dat doet — zelfde
momentopname, zelfde geheugen en nieuwsgierigheid — en klokt elk stuk
apart: taken maken, antwoorden, nakijken, geheugen, partij bouwen, en het
rekenwerk op de kaart. Leest en meet alleen; er wordt niets bewaard.

Let op: de kaart hier (P100) is een andere dan op de Z490 (3070 Ti), dus
de kaart-tijden zijn niet één op één; de CPU-tijden wel ongeveer
(Xeon E5-2690 v4 hier tegen i7-11700 daar — die is eerder sneller).

  venv/bin/python fase1/kloof-meting.py <checkpoint> [stappen]
"""
import sys
import time
from collections import defaultdict

sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinism
determinism.lock(20260808)                  # zelfde zaad als life.py

import torch
import bridge
import exams
import learning
import snapshot
import world
import tasks as tasks_module
from learning import Learner

PAD = sys.argv[1]
STAPPEN = int(sys.argv[2]) if len(sys.argv) > 2 else 40

klok = defaultdict(float)
tel = defaultdict(int)


def meet(naam, f):
    """Wikkel een functie: klok hem, met de kaart leeggelopen aan beide
    kanten, zodat kaartwerk niet stiekem bij het volgende stuk telt."""
    def binnen(*a, **k):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        try:
            return f(*a, **k)
        finally:
            torch.cuda.synchronize()
            klok[naam] += time.perf_counter() - t0
            tel[naam] += 1
    return binnen


learner = Learner(batch_size=64)
content = snapshot.read(PAD, device=learner.device)
learner.adopt_shape((content.get("extra") or {}).get("vorm"))
begin = snapshot.restore(content, learner.core, learner.optimizer,
                         learner.device) + 1
learner.steps = begin - 1
extra = content.get("extra") or {}
vorm = extra.get("vorm")
if vorm:
    learner.adopt_window(bridge.translate_spec(vorm).get("window") or 0)
if "geheugen" in extra:
    learner.restore(extra)
print(f"momentopname stap {begin - 1:,} · venster {learner.core.window} · "
      f"geheugen {len(learner.memory):,} · {learner.device}"
      .replace(",", "."))

# --- de wikkels --------------------------------------------------------------
world.learning_tasks = meet("taken maken (wereld)", world.learning_tasks)
learner.answer = meet("antwoorden (kaart, autoregressief)", learner.answer)
learner._make_batch = meet("partij bouwen (tekens→tensor)", learner._make_batch)
_step_real = learner._step_real
def _step_gemeten(chunk):
    # partij bouwen wordt apart geklokt; de rest van _step_real is de kaart
    torch.cuda.synchronize(); t0 = time.perf_counter()
    try:
        return _step_real(chunk)
    finally:
        torch.cuda.synchronize()
        klok["leren (kaart: voor/achter/optimizer)"] += time.perf_counter() - t0
        tel["leren (kaart: voor/achter/optimizer)"] += 1
learner._step_real = _step_gemeten
learner.memory.remember = meet("geheugen: onthouden", learner.memory.remember)
learner.memory.replay = meet("geheugen: herhalen kiezen", learner.memory.replay)
learning._as_task = meet("geheugen: herinnering→taak", learning._as_task)
learner.curiosity.pick = meet("nieuwsgierigheid: kiezen", learner.curiosity.pick)
learner.curiosity.update = meet("nieuwsgierigheid: bijwerken", learner.curiosity.update)
exams.material = meet("proefwerkslot ophalen", exams.material)
# nakijken zit binnen work(); we tellen het via Task.check
tasks_module.Task.check = meet("nakijken (check)", tasks_module.Task.check)

# --- de stappen ------------------------------------------------------------
totaal0 = time.perf_counter()
per_stap = []
pogingen = 0
for stap in range(begin, begin + STAPPEN):
    torch.cuda.synchronize(); t0 = time.perf_counter()
    r = learner.work(stap)
    torch.cuda.synchronize(); dt = time.perf_counter() - t0
    per_stap.append((dt, r["score"] is not None, r["family"], r["depth"]))
    if r["score"] is not None:
        pogingen += 1
totaal = time.perf_counter() - totaal0

# De partij bouwen zit binnen _step_real: eruit halen zodat "leren (kaart)"
# echt alleen de kaart is.
klok["leren (kaart: voor/achter/optimizer)"] -= klok["partij bouwen (tekens→tensor)"]
# Nakijken en onthouden zitten binnen work() maar buiten answer/learn —
# behalve onthouden-in-learn; dat is al apart geklokt (zelfde wikkel).

print(f"\n{STAPPEN} stappen, {pogingen} met poging, {totaal:.1f} s totaal, "
      f"{totaal / STAPPEN * 1000:.0f} ms/stap")
met = [d for d, p, *_ in per_stap if p]
zonder = [d for d, p, *_ in per_stap if not p]
if met:
    print(f"  met poging  : {sum(met) / len(met):.2f} s  (n={len(met)})")
if zonder:
    print(f"  zonder      : {sum(zonder) / len(zonder):.2f} s  (n={len(zonder)})")

print("\nwaar de tijd zit (over alle stappen):")
verklaard = 0.0
for naam, t in sorted(klok.items(), key=lambda kv: -kv[1]):
    verklaard += t
    print(f"  {naam:<38} {t:>7.2f} s  {t / totaal:>5.1%}  "
          f"({tel[naam]} keer, {t / max(1, tel[naam]) * 1000:.1f} ms per keer)")
rest = totaal - verklaard
print(f"  {'rest (Python-lijm in work/learn)':<38} {rest:>7.2f} s  {rest / totaal:>5.1%}")

kaart = klok["antwoorden (kaart, autoregressief)"] + \
    klok["leren (kaart: voor/achter/optimizer)"]
print(f"\nkaart samen {kaart:.1f} s = {kaart / totaal:.0%}; "
      f"de rest ({totaal - kaart:.1f} s = {(totaal - kaart) / totaal:.0%}) "
      f"is CPU — dat is de kloof.")
