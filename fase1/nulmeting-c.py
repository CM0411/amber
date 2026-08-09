"""
De nulmeting van C — hoe erg vergeet ze?

Dit is het getal waar het project om bestaat. Twee runs, identiek op één ding na:

  * **zonder herhaling** — geen enkele bescherming tegen vergeten. Dat is de
    nulmeting: hoe groot is het probleem eigenlijk?
  * **met herhaling** — de helft van elke partij komt uit het herhaalgeheugen,
    door de flessenhals. Het eerste mechanisme, afgerekend tegen die nulmeting

De verleiding is om meteen herhaling in te bouwen omdat het werkt. Maar dan
weet je nooit hoe groot het probleem was, en dus ook niet of je het hebt
opgelost of alleen bedekt.

Beide runs krijgen hetzelfde zaad, hetzelfde leerplan en dezelfde taken. Het
enige verschil is het mechanisme.

Draaien:  venv/bin/python fase1/nulmeting-c.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "kern"))

import determinisme                        # MOET vóór torch
determinisme.zet_vast(20260808)

import logboek
import meetlus
import taken
from leren import Leerder

PLAN = [("rekenen", 1), ("puzzel", 1)]
STAPPEN_PER_FAMILIE = 500
PARTIJ = 32
MAP = "/home/arch/amber-werk/fase1/nulmeting"
VERSLAG = "/home/arch/amber-werk/fase1/nulmeting-c.md"


def een_run(naam, herhaling, log):
    determinisme.zet_vast(20260808)        # allebei vanaf hetzelfde punt
    leerder = Leerder(partij=PARTIJ, herhaling=herhaling)

    # Gelijke partijen én gelijk aantal stappen: allebei de runs doen precies
    # evenveel rekenwerk. Herhaling gaat dus ten koste van nieuw materiaal en
    # komt er niet bovenop. Dat is de eerlijke vergelijking, want rekenkracht
    # is hier de schaarse zaak — ze draait onder een geluidsplafond.
    nieuw = leerder.nieuw_per_partij
    print(f"\n{'=' * 66}")
    print(f"{naam}   (herhaling {herhaling:.0%})")
    print(f"  partij {PARTIJ} = {nieuw} nieuw + {PARTIJ - nieuw} herhaald, "
          f"{STAPPEN_PER_FAMILIE} stappen per familie")
    print("=" * 66)

    metingen = [{"fase": "begin", "scores": meetlus.meet_alles(leerder, aantal=100)}]
    print(f"  begin:            " + toon(metingen[0]["scores"]))

    for familie, graad in PLAN:
        t0 = time.perf_counter()
        leerder.leer(taken.leerreeks(familie, graad, STAPPEN_PER_FAMILIE * nieuw))
        scores = meetlus.meet_alles(leerder, aantal=100)
        metingen.append({"fase": f"na {familie}/{graad}", "scores": scores})
        print(f"  na {familie}/{graad}:".ljust(20)
              + toon(scores)
              + f"   ({time.perf_counter() - t0:.0f} s)")
        log.schrijf("meting", run=naam, fase=f"na {familie}/{graad}",
                    scores={f"{f}/{g}": v for (f, g), v in scores.items()})

    uitkomst = {"plan": [list(p) for p in PLAN], "metingen": metingen,
                "vergeten": meetlus._vergeten(metingen, PLAN),
                "nieuw_per_partij": nieuw,
                "stappen": leerder.stappen,
                "nieuwe_taken": STAPPEN_PER_FAMILIE * nieuw * len(PLAN)}
    print()
    print("  " + meetlus.tabel(uitkomst).replace("\n", "\n  "))
    print(f"\n  {leerder.stappen} stappen, "
          f"{uitkomst['nieuwe_taken']} nieuwe taken gezien")
    print(f"  geheugen: {leerder.geheugen.stand()}")
    return uitkomst


def toon(scores):
    return "  ".join(f"{f}/{g} {v:>4.0%}"
                     for (f, g), v in scores.items() if (f, g) in PLAN)


os.makedirs(MAP, exist_ok=True)
log = logboek.Logboek(f"{MAP}/logboek.jsonl")

zonder = een_run("ZONDER herhaling — de nulmeting", 0.0, log)
met = een_run("MET herhaling", 0.5, log)

log.rust(reden="nulmeting klaar")
log.sluit()

# --- de vergelijking -------------------------------------------------------

z = zonder["vergeten"][0]        # rekenen/1, het onderwerp dat als eerste kwam
m = met["vergeten"][0]

print(f"\n{'=' * 66}")
print("DE NULMETING VAN C")
print("=" * 66)
print(f"  rekenen graad 1, na het leren van puzzels:")
print(f"    zonder herhaling behouden: "
      f"{'—' if z['behouden'] is None else format(z['behouden'], '.0%')}")
print(f"    met herhaling behouden:    "
      f"{'—' if m['behouden'] is None else format(m['behouden'], '.0%')}")

with open(VERSLAG, "w") as f:
    f.write("# De nulmeting van C\n\n")
    f.write(f"Leerplan: {' → '.join(f'{a}/{b}' for a, b in PLAN)}, "
            f"{STAPPEN_PER_FAMILIE} stappen per familie, partij {PARTIJ}.\n")
    f.write("Beide runs hetzelfde zaad, dezelfde taken, hetzelfde plan. "
            "Het enige verschil is het mechanisme.\n\n")
    f.write("Gelijke partijen én gelijk aantal stappen: beide runs doen precies "
            "evenveel rekenwerk.\nHerhaling gaat ten koste van nieuw materiaal "
            "en komt er niet bovenop.\n\n")
    for naam, uit in (("Zonder herhaling — de nulmeting", zonder),
                      ("Met herhaling", met)):
        f.write(f"## {naam}\n\n")
        f.write(f"{uit['stappen']} stappen, partij {PARTIJ} "
                f"({uit['nieuw_per_partij']} nieuw + "
                f"{PARTIJ - uit['nieuw_per_partij']} herhaald), "
                f"{uit['nieuwe_taken']} nieuwe taken gezien.\n\n")
        f.write(f"{meetlus.tabel(uit)}\n\n")
    f.flush()
    os.fsync(f.fileno())
print(f"\nVerslag: {VERSLAG}")
