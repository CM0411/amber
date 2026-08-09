"""
Hoeveel herhaling? — over meerdere zaden.

De vorige meting liet zien dat 25% herhaling "geen bescherming" op beide assen
verslaat, en dat 50% wél een prijs heeft. Maar dat rustte op één zaad, en het
is de instelling die hierna standaard gebruikt gaat worden. Zo'n keuze mag niet
op één toevallige run rusten.

Vijf instellingen over vier zaden. Per zaad hetzelfde plan, dezelfde taken en
even veel stappen met een even grote partij — het enige verschil is hoeveel van
elke partij uit het geheugen komt.

Er wordt alleen gemeten op de twee families uit het plan. Alle vijftien
combinaties meten kost zeven keer zoveel en zegt hier niets extra's.

Draaien:  venv/bin/python fase1/hoeveel-herhaling.py
"""

import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "kern"))

import determinisme                        # MOET vóór torch
determinisme.zet_vast(1)

import meetlus
import taken
from leren import Leerder

PLAN = [("rekenen", 1), ("puzzel", 1)]
STAPPEN_PER_FAMILIE = 500
PARTIJ = 32
ZADEN = [20260808, 7, 424242, 31337]
DELEN = [0.0, 0.125, 0.25, 0.375, 0.5]
VERSLAG = "/home/arch/amber-werk/fase1/hoeveel-herhaling.md"


def meet_plan(leerder):
    return {(f, g): meetlus.meet(leerder, f, g, 100) for f, g in PLAN}


def een_run(zaad, deel):
    determinisme.zet_vast(zaad)
    leerder = Leerder(partij=PARTIJ, herhaling=deel)
    nieuw = leerder.nieuw_per_partij

    top = None
    for i, (familie, graad) in enumerate(PLAN):
        leerder.leer(taken.leerreeks(familie, graad, STAPPEN_PER_FAMILIE * nieuw))
        if i == 0:
            top = meet_plan(leerder)[("rekenen", 1)]
    eind = meet_plan(leerder)

    behouden = (1 - (top - eind[("rekenen", 1)]) / top) if top > 1e-9 else None
    return {"top": top, "eind": eind[("rekenen", 1)],
            "behouden": behouden, "puzzel": eind[("puzzel", 1)],
            "nieuw_per_partij": nieuw}


print("=" * 72)
print("Hoeveel herhaling? — vier zaden")
print("=" * 72)
print(f"Plan: {' → '.join(f'{a}/{b}' for a, b in PLAN)}, "
      f"{STAPPEN_PER_FAMILIE} stappen per familie, partij {PARTIJ}")
print(f"Zaden: {ZADEN}")

alles = {}
begin = time.perf_counter()
for deel in DELEN:
    alles[deel] = []
    for zaad in ZADEN:
        t0 = time.perf_counter()
        uit = een_run(zaad, deel)
        alles[deel].append(uit)
        print(f"  herhaling {deel:>5.1%}  zaad {zaad:>9}  "
              f"top {uit['top']:>4.0%}  behouden "
              f"{('—' if uit['behouden'] is None else format(uit['behouden'], '.0%')):>4}  "
              f"puzzel {uit['puzzel']:>4.0%}   ({time.perf_counter() - t0:.0f} s)")
    print()

print(f"totaal {(time.perf_counter() - begin) / 60:.0f} minuten\n")


def samenvatten(waarden):
    return (statistics.mean(waarden), min(waarden), max(waarden))


kop = (f"{'herhaling':<11} {'nieuw':>6} {'rekenen top':>20} "
       f"{'behouden':>20} {'puzzel':>20}")
regels = [kop, "-" * len(kop)]
for deel in DELEN:
    runs = alles[deel]
    t = samenvatten([r["top"] for r in runs])
    b = samenvatten([r["behouden"] for r in runs if r["behouden"] is not None])
    p = samenvatten([r["puzzel"] for r in runs])
    regels.append(
        f"{deel:<11.1%} {runs[0]['nieuw_per_partij']:>6} "
        f"{t[0]:>10.0%} ({t[1]:.0%}–{t[2]:.0%}) "
        f"{b[0]:>10.0%} ({b[1]:.0%}–{b[2]:.0%}) "
        f"{p[0]:>10.0%} ({p[1]:.0%}–{p[2]:.0%})"
    )
tabel = "\n".join(regels)
print("=" * 72)
print(tabel)
print("=" * 72)
print("gemiddelde over vier zaden, met de laagste en hoogste run erachter")

with open(VERSLAG, "w") as f:
    f.write("# Hoeveel herhaling?\n\n")
    f.write(f"Plan: {' → '.join(f'{a}/{b}' for a, b in PLAN)}, "
            f"{STAPPEN_PER_FAMILIE} stappen per familie, partij {PARTIJ}.\n")
    f.write(f"Vier zaden: {ZADEN}. Alle opstellingen doen evenveel stappen "
            f"met een even grote partij.\n\n")
    f.write("```\n" + tabel + "\n```\n\n")
    f.write("Gemiddelde over vier zaden, met de laagste en hoogste run "
            "erachter.\n\n## Per run\n\n")
    f.write("| herhaling | zaad | rekenen top | behouden | puzzel |\n")
    f.write("|---|---:|---:|---:|---:|\n")
    for deel in DELEN:
        for zaad, r in zip(ZADEN, alles[deel]):
            bh = "—" if r["behouden"] is None else f"{r['behouden']:.0%}"
            f.write(f"| {deel:.1%} | {zaad} | {r['top']:.0%} | {bh} | "
                    f"{r['puzzel']:.0%} |\n")
    f.flush()
    os.fsync(f.fileno())
print(f"\nVerslag: {VERSLAG}")
