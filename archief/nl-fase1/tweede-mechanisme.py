"""
Het tweede C-mechanisme, afgerekend tegen het eerste.

De lat uit de nulmeting: een mechanisme moet winnen op **behoud per bestede
rekenstap**, niet op behoud alleen. Rekenkracht is de schaarse zaak — ze draait
altijd onder een geluidsplafond.

Twee mechanismen, en het verschil zit hem precies in wat ze kosten:

  **herhaling** — een deel van elke partij komt uit het geheugen. Kost plaats
  in de partij: elke herhaalde taak is een nieuwe die er niet in kon.

  **de rem** — na het leren van A vaststellen welke gewichten daarvoor belangrijk
  waren, en die tijdens B afremmen. Kost géén plaats in de partij; alle
  voorbeelden blijven nieuw. Alleen eenmalig wat rekenwerk om het belang vast
  te stellen, plus een vermenigvuldiging per gewicht per stap.

Van allebei een reeks sterktes, want één instelling per mechanisme kiezen en
dan vergelijken zegt meer over de keuze dan over de mechanismen.

Draaien:  venv/bin/python fase1/tweede-mechanisme.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "kern"))

import determinisme                        # MOET vóór torch
determinisme.zet_vast(20260808)

import meetlus
import taken
from leren import Leerder

PLAN = [("rekenen", 1), ("puzzel", 1)]
STAPPEN_PER_FAMILIE = 500
PARTIJ = 32
ZAAD = 20260808
VERSLAG = "/home/arch/amber-werk/fase1/tweede-mechanisme.md"

OPSTELLINGEN = [
    ("geen bescherming",   dict()),
    ("herhaling 25%",      dict(herhaling=0.25)),
    ("herhaling 50%",      dict(herhaling=0.50)),
    ("rem, zwak (1e2)",    dict(remkracht=1e2)),
    ("rem, midden (1e4)",  dict(remkracht=1e4)),
    ("rem, sterk (1e6)",   dict(remkracht=1e6)),
]


def een_run(naam, instelling):
    determinisme.zet_vast(ZAAD)
    leerder = Leerder(partij=PARTIJ, **instelling)
    nieuw = leerder.nieuw_per_partij

    print(f"\n{'-' * 68}")
    print(f"{naam}   |   {nieuw} nieuw + {PARTIJ - nieuw} herhaald per partij")

    scores = [meetlus.meet_alles(leerder, aantal=100)]
    tijd = 0.0
    geleerd = None

    for i, (familie, graad) in enumerate(PLAN):
        stof = taken.leerreeks(familie, graad, STAPPEN_PER_FAMILIE * nieuw)
        t0 = time.perf_counter()
        leerder.leer(stof)
        tijd += time.perf_counter() - t0

        # Consolideren gebeurt ná het eerste onderwerp: dán is er iets te
        # beschermen. Dit is meteen de zwakke plek van deze aanpak — er moet
        # een moment zijn waarop je weet dat een onderwerp klaar is.
        if i == 0 and leerder.remkracht > 0:
            t0 = time.perf_counter()
            leerder.consolideer(stof)
            tijd += time.perf_counter() - t0
            geleerd = stof

        scores.append(meetlus.meet_alles(leerder, aantal=100))
        print(f"  na {familie}/{graad}:".ljust(18)
              + "  ".join(f"{f}/{g} {scores[-1][(f, g)]:>4.0%}" for f, g in PLAN))

    r = ("rekenen", 1)
    p = ("puzzel", 1)
    top = scores[1][r]
    eind = scores[-1][r]
    behouden = (1 - (top - eind) / top) if top > 1e-9 else None

    uit = {
        "naam": naam,
        "top": top,
        "eind": eind,
        "behouden": behouden,
        "puzzel": scores[-1][p],
        "seconden": tijd,
        "stappen": leerder.stappen,
        "nieuwe_taken": STAPPEN_PER_FAMILIE * nieuw * len(PLAN),
    }
    print(f"  behouden {('—' if behouden is None else format(behouden, '.0%')):>4}"
          f"   |   {tijd:.0f} s   |   {uit['nieuwe_taken']} nieuwe taken")
    return uit


print("=" * 68)
print("Twee mechanismen tegen de nulmeting")
print("=" * 68)
print(f"Plan: {' → '.join(f'{a}/{b}' for a, b in PLAN)}, "
      f"{STAPPEN_PER_FAMILIE} stappen per familie, partij {PARTIJ}, zaad {ZAAD}")

uitkomsten = [een_run(naam, inst) for naam, inst in OPSTELLINGEN]

# --- de tabel --------------------------------------------------------------

kop = (f"\n{'opstelling':<20} {'rekenen top':>11} {'aan het eind':>13} "
       f"{'behouden':>9} {'puzzel':>7} {'nieuwe taken':>13} {'tijd':>7}")
regels = [kop, "-" * len(kop)]
for u in uitkomsten:
    regels.append(
        f"{u['naam']:<20} {u['top']:>10.0%} {u['eind']:>12.0%} "
        f"{('—' if u['behouden'] is None else format(u['behouden'], '.0%')):>9} "
        f"{u['puzzel']:>6.0%} {u['nieuwe_taken']:>13,} {u['seconden']:>6.0f}s"
    )
tabel = "\n".join(regels)
print("\n" + "=" * 68)
print(tabel)
print("=" * 68)

with open(VERSLAG, "w") as f:
    f.write("# Het tweede C-mechanisme\n\n")
    f.write(f"Plan: {' → '.join(f'{a}/{b}' for a, b in PLAN)}, "
            f"{STAPPEN_PER_FAMILIE} stappen per familie, partij {PARTIJ}, "
            f"zaad {ZAAD}.\nAlle opstellingen doen evenveel stappen met een "
            f"even grote partij.\n\n")
    f.write("```\n" + tabel + "\n```\n")
    f.flush()
    os.fsync(f.fileno())
print(f"\nVerslag: {VERSLAG}")
