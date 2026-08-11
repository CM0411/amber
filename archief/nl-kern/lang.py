import sys, os
sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinisme; determinisme.zet_vast(99)
import leren, wereld, proefwerken, time
L = leren.Leerder(herhaling=0.0, partij=64)
slot = proefwerken.stof()
proef = wereld.leerreeks("rekenen", 2, 200, vanaf=600_000, uitsluiten=slot)
t0 = time.perf_counter(); gezien = 0
for ronde in range(1, 26):
    stof = wereld.leerreeks("rekenen", 2, 64*100, vanaf=1_000_000+ronde*20000, uitsluiten=slot)
    fout = L.leer(stof); gezien += len(stof)
    geg = L.antwoorden(proef, hoogstens=40)
    goed = sum(1 for t,a in zip(proef,geg) if t.nakijk(a))
    print(f"  {gezien:>7,} taken | fout {fout:.3f} | rekenen d2: {goed/2:>4.0f}%  "
          f"({time.perf_counter()-t0:.0f}s)", flush=True)
