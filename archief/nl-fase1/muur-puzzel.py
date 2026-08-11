"""Valideert de puzzelfix: komt ze met de nieuwe uitwerking wél door diepte 3?

Vers netwerkje, alleen puzzels diepte 1-3. Vóór de fix stond diepte 3 op 0%
omdat de uitwerking het antwoord niet opleverde. Als dit werkt, mag de fix
mee in de volgende grote run.
"""
import sys, os
sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinisme; determinisme.zet_vast(4001)
import leren, wereld, proefwerken, time

L = leren.Leerder(partij=64)
slot = proefwerken.stof()
proef = {d: wereld.leerreeks("puzzel", d, 100, vanaf=600_000, uitsluiten=slot)
         for d in (1, 2, 3)}

gezien = 0
t0 = time.perf_counter()
for ronde in range(1, 26):
    for d in (1, 2, 3):
        stof = wereld.leerreeks("puzzel", d, 64 * 12,
                                vanaf=700_000 + ronde * 30_000, uitsluiten=slot)
        L.leer(stof); gezien += len(stof)
    scores = []
    for d in (1, 2, 3):
        geg = L.antwoorden(proef[d], hoogstens=leren.ruimte_voor(d, "puzzel"))
        scores.append(sum(1 for t, a in zip(proef[d], geg) if t.nakijk(a)))
    print(f"{gezien:>7,} taken | d1 {scores[0]:>3}%  d2 {scores[1]:>3}%  "
          f"d3 {scores[2]:>3}%  ({time.perf_counter()-t0:.0f}s)", flush=True)
