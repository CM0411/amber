"""De C-meting op de echte wereld, over meerdere zaden. Draait onbeheerd.

Leer rekenen (diepte 2), meet. Leer daarna puzzel (diepte 2), meet opnieuw.
Wat rekenen inlevert is het vergeten. Vier herhalingsinstellingen, vijf zaden,
alles op één P100 in de stille stand — naast run 3 op de X399.

De eerdere sweep draaide op de oude catalogus zonder uitwerkingen; dit is de
nulmeting die bij haar echte wereld hoort.
"""
import sys, os, time
sys.path.insert(0, "/home/arch/amber-werk/kern")
import determinisme; determinisme.zet_vast(1)
import leren, wereld, proefwerken

ZADEN = [20260809, 7, 424242, 31337, 99]
DELEN = [0.0, 0.125, 0.25, 0.375]
STAPPEN = 500
VERSLAG = "/home/arch/amber-werk/fase1/c-zaden.md"
slot = proefwerken.stof()

def meet(L, f, d):
    proef = wereld.leerreeks(f, d, 100, vanaf=600_000, uitsluiten=slot)
    geg = L.antwoorden(proef, hoogstens=leren.ruimte_voor(d, f))
    return sum(1 for t, a in zip(proef, geg) if t.nakijk(a)) / 100

regels = []
t0 = time.perf_counter()
for deel in DELEN:
    for zaad in ZADEN:
        determinisme.zet_vast(zaad)
        L = leren.Leerder(partij=64, herhaling=deel)
        n = L.nieuw_per_partij
        L.leer(wereld.leerreeks("rekenen", 2, STAPPEN * n, uitsluiten=slot))
        top = meet(L, "rekenen", 2)
        L.leer(wereld.leerreeks("puzzel", 2, STAPPEN * n, vanaf=900_000,
                                uitsluiten=slot))
        eind = meet(L, "rekenen", 2)
        puzzel = meet(L, "puzzel", 2)
        behouden = (1 - (top - eind) / top) if top > 1e-9 else None
        r = {"deel": deel, "zaad": zaad, "top": top, "eind": eind,
             "behouden": behouden, "puzzel": puzzel}
        regels.append(r)
        b = "—" if behouden is None else f"{behouden:.0%}"
        print(f"herhaling {deel:>5.1%}  zaad {zaad:>9}  top {top:>4.0%}  "
              f"behouden {b:>4}  puzzel {puzzel:>4.0%}  "
              f"({(time.perf_counter()-t0)/60:.0f} min)", flush=True)
        # tussenstand wegschrijven: een crash kost dan geen resultaten
        with open(VERSLAG, "w") as f:
            f.write("# C over zaden — de echte wereld\n\n")
            f.write("| herhaling | zaad | top | behouden | puzzel |\n|---:|---:|---:|---:|---:|\n")
            for x in regels:
                bb = "—" if x["behouden"] is None else f"{x['behouden']:.0%}"
                f.write(f"| {x['deel']:.1%} | {x['zaad']} | {x['top']:.0%} | {bb} | {x['puzzel']:.0%} |\n")
            f.flush(); os.fsync(f.fileno())
print("KLAAR")
