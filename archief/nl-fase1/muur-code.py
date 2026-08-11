"""De code-muur: is diepte 4 honger of een ontwerpfout?

Vers netwerkje, alleen code diepte 3-4. Rekenen ging met genoeg oefening van
2% naar 94% — als code hetzelfde doet is het honger en lost de volgende lange
run het vanzelf op. Blijft hij hangen, dan zit er iets scheef in de opgaven
zelf en moeten we kijken, net als bij puzzel.
"""
import sys, os
sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinisme; determinisme.zet_vast(4002)
import leren, wereld, proefwerken, time

L = leren.Leerder(partij=64)
slot = proefwerken.stof()
proef = {d: wereld.leerreeks("code", d, 100, vanaf=600_000, uitsluiten=slot)
         for d in (3, 4)}

gezien = 0
t0 = time.perf_counter()
for ronde in range(1, 26):
    for d in (3, 4):
        stof = wereld.leerreeks("code", d, 64 * 18,
                                vanaf=700_000 + ronde * 30_000, uitsluiten=slot)
        L.leer(stof); gezien += len(stof)
    scores = []
    for d in (3, 4):
        geg = L.antwoorden(proef[d], hoogstens=leren.ruimte_voor(d, "code"))
        scores.append(sum(1 for t, a in zip(proef[d], geg) if t.nakijk(a)))
    print(f"{gezien:>7,} taken | d3 {scores[0]:>3}%  d4 {scores[1]:>3}%  "
          f"({time.perf_counter()-t0:.0f}s)", flush=True)
