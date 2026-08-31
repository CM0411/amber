"""Eigen stof — de eerste echte trede van G (31 aug 2026, Cleys akkoord).

Zij maakt zelf oefenstof voor haar zwakste rekendeel (deling). De aanloop:
een paar voorgedane sommen (deterministisch uit de dag-datum, alle juist).
Dan schrijft zíj de volgende som, met antwoord — haar eigen brein, op de
CPU, uit de laatste momentopname, buiten de trainer om.

De rechter rekent exact na. Alleen een som die klopt, die níét is
overgeschreven van de aanloop en die vandaag nog niet gemaakt is, wordt
een les in de brievenbus (bron "eigen stof (G)") — en gaat dus pas op de
rungrens haar geheugen in, zoals elke les.

Grenzen: hooguit EIGEN_PER_DAG lessen per dag, hooguit één maakronde per
TUSSEN_UREN uur. Alles — ook elke mislukte poging — staat in
rapport/eigen-stof.jsonl: zo zien we haar G-leercurve vanaf nul ontstaan.

Draait mee in amber-rapport.service (drop-in, als laatste stap) en mag die
keten nooit breken: elke uitgang is exit 0.

  python3 eigen-stof.py            # maken (met dagtaks en uurrem)
  python3 eigen-stof.py --droog    # alleen printen, niets schrijven
"""
import json
import os
import re
import sys
import time

RAPPORT = "/home/arch/rapport"
LOG = f"{RAPPORT}/eigen-stof.jsonl"
STAND = f"{RAPPORT}/eigen-stof-stand.json"
BUS = "/home/arch/amber-werk/fase1/brievenbus.jsonl"
KERN = "/home/arch/amber-werk/kern"
OPNAME = "/home/arch/amber-werk/fase1/leven/momentopname.pt"
DROOG = "--droog" in sys.argv

EIGEN_PER_DAG = 10      # meer lessen dan dit maakt ze niet op één dag
TUSSEN_UREN = 2         # en niet vaker dan eens per zoveel uur
POGINGEN = 12           # maakbeurten per ronde (elk met een eigen aanloop)
# elke nette som telt (bij de eerste proef maakte ze kloppende keer-, plus-
# en minsommen maar ontweek ze het delen van de aanloop — dat ontwijken is
# zelf een meting: het logboek telt per som of het deling was)
SOM = re.compile(r"(\d{1,4}) ([+*/-]) (\d{1,4}) = (-?\d{1,4})")


def _klopt(a, op, b, c):
    if op == "+":
        return a + b == c
    if op == "-":
        return a - b == c
    if op == "*":
        return a * b == c
    return b != 0 and a % b == 0 and a // b == c


def lees(pad, anders):
    try:
        with open(pad) as f:
            return json.load(f)
    except Exception:
        return anders


def aanloop(zaad):
    """Drie juiste deelsommen, deterministisch uit het zaad — geen import
    van de wereld nodig: dit is de aanloop, niet de leerstof."""
    x = zaad or 1
    paren = []
    while len(paren) < 3:
        x = (x * 1103515245 + 12345) % (1 << 31)
        b = 3 + x % 10          # deler 3..12
        x = (x * 1103515245 + 12345) % (1 << 31)
        c = 3 + x % 10          # uitkomst 3..12
        if (b, c) not in paren:
            paren.append((b, c))
    return " ; ".join(f"{b * c} / {b} = {c}" for b, c in paren) + " ; "


def hoofd():
    nu = time.time()
    vandaag = time.strftime("%Y-%m-%d")
    stand = lees(STAND, {})
    if stand.get("dag") != vandaag:
        stand = {"dag": vandaag, "gemaakt": 0, "laatste": 0.0}
    if not DROOG:
        if nu - float(stand.get("laatste") or 0) < TUSSEN_UREN * 3600:
            return
        if stand["gemaakt"] >= EIGEN_PER_DAG:
            return

    # haar brein wakker maken, precies zoals het zelfrapport dat doet
    sys.path.insert(0, KERN)
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    import determinism
    determinism.lock(1)
    import torch
    import learning
    import snapshot
    import bridge
    import tasks as _tasks
    L = learning.Learner(batch_size=1)
    inhoud = snapshot.read(OPNAME, device="cpu")
    extra = inhoud.get("extra") or {}
    if extra.get("vorm"):
        L.adopt_shape(bridge.translate_spec(extra["vorm"]))
    snapshot.restore(inhoud, L.core, None, "cpu")
    stap = inhoud.get("step")

    zaad = int(vandaag.replace("-", ""))
    al_vandaag = set()
    for regel in open(LOG).read().splitlines() if os.path.exists(LOG) else []:
        try:
            r = json.loads(regel)
        except Exception:
            continue
        if r.get("dag") == vandaag and r.get("geldig"):
            al_vandaag.add(r.get("som"))

    lessen = []
    logregels = []
    for i in range(POGINGEN):
        if stand["gemaakt"] + len(lessen) >= EIGEN_PER_DAG and not DROOG:
            break
        start = aanloop(zaad + 7919 * (i + 1))
        taak = _tasks.Task(family="vraag", grade=1, number=0,
                           problem=start, solution="")
        with torch.no_grad():
            uit = L.answer([taak], at_most=24)[0].strip()
        r = {"tijd": nu, "dag": vandaag, "stap": stap, "aanloop": start,
             "zij": uit, "geldig": False, "reden": "", "sommen": []}
        treffers = SOM.findall(uit)
        if not treffers:
            r["reden"] = "geen som te lezen"
        for a, op, b, c in treffers:
            a, b, c = int(a), int(b), int(c)
            heel = f"{a} {op} {b} = {c}"
            if heel in start:
                r["sommen"].append({"som": heel, "goed": False,
                                    "reden": "overgeschreven uit de aanloop"})
            elif heel in al_vandaag:
                r["sommen"].append({"som": heel, "goed": False,
                                    "reden": "vandaag al gemaakt"})
            elif not _klopt(a, op, b, c):
                r["sommen"].append({"som": heel, "goed": False,
                                    "reden": "rekent niet"})
            else:
                r["sommen"].append({"som": heel, "goed": True,
                                    "deling": op == "/"})
                al_vandaag.add(heel)
                if stand["gemaakt"] + len(lessen) < EIGEN_PER_DAG or DROOG:
                    lessen.append((f"{a} {op} {b}", str(c), heel))
        if any(s["goed"] for s in r["sommen"]):
            r["geldig"] = True
            r["reden"] = "goedgekeurd"
        elif treffers:
            r["reden"] = r["sommen"][0]["reden"]
        logregels.append(r)

    deling = sum(1 for _, _, heel in lessen if " / " in heel)
    if DROOG:
        for r in logregels:
            print(("GOED " if r["geldig"] else "mis  ")
                  + f"[{r['reden']}] zij: {r['zij']!r}")
        print(f"-> {len(lessen)} lessen uit {len(logregels)} beurten, "
              f"waarvan {deling} deling")
        return

    with open(LOG, "a") as f:
        for r in logregels:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    if lessen:
        import fcntl
        with open(BUS + ".slot", "w") as s:
            fcntl.flock(s, fcntl.LOCK_EX)
            with open(BUS, "a") as f:
                for som, antwoord, heel in lessen:
                    f.write(json.dumps({
                        "tijd": time.time(),
                        "wanneer": time.strftime("%Y-%m-%d %H:%M"),
                        "soort": "les", "bron": "eigen stof (G)",
                        "vraag": som, "antwoord": antwoord,
                        "bezorgd": False,
                    }, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())

    stand["gemaakt"] += len(lessen)
    stand["laatste"] = nu
    with open(STAND + ".deel", "w") as f:
        json.dump(stand, f)
    os.replace(STAND + ".deel", STAND)
    print(f"eigen stof: {len(lessen)} les(sen) uit {len(logregels)} beurten "
          f"({deling} deling); vandaag {stand['gemaakt']}/{EIGEN_PER_DAG}")


if __name__ == "__main__":
    try:
        hoofd()
    except Exception as e:
        # nooit de rapportketen breken
        print("eigen stof haperde:", e)
    sys.exit(0)
