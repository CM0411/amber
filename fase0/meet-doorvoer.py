"""
Wat kost de stilte?

De werkstand is 696 MHz. Dit meet wat daar tegenover staat aan rekenkracht,
zodat de planning van fase 1 op een getal rust en niet op een schatting.

Drie metingen, alle drie in de stille stand — dit script maakt geen herrie:

  1. doorvoer per matrixgrootte, één kaart, tegenover de al gemeten waarden
     bij de standaardklok
  2. verbruik en temperatuur van beide kaarten samen onder belasting
  3. wat determinisme aan snelheid kost. De roadmap zegt "het kost snelheid";
     dat is nooit nagerekend

Draaien:  venv/bin/python fase0/meet-doorvoer.py
"""

import os
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import statistics
import subprocess
import threading
import time

import torch

WERKSTAND = 696
GROOTTES = (1024, 2048, 4096, 8192)

# Gemeten op 8 aug 2026 bij de standaardklok (1189 MHz toegepast, boost tot
# ~1290 onder belasting), zonder determinisme. Kaart 0, fp32.
VOL_VERMOGEN = {1024: 5.27, 2048: 6.31, 4096: 8.02, 8192: 8.64}


def smi(vraag):
    r = subprocess.run(["nvidia-smi", f"--query-gpu={vraag}",
                        "--format=csv,noheader,nounits"],
                       capture_output=True, text=True)
    return [x.strip() for x in r.stdout.strip().splitlines()]


def doorvoer(n, dtype=torch.float32, kaart=0, herhaal=10):
    apparaat = f"cuda:{kaart}"
    a = torch.randn(n, n, device=apparaat, dtype=dtype)
    b = torch.randn(n, n, device=apparaat, dtype=dtype)
    for _ in range(3):
        a @ b
    torch.cuda.synchronize(kaart)
    t0 = time.perf_counter()
    for _ in range(herhaal):
        a @ b
    torch.cuda.synchronize(kaart)
    duur = (time.perf_counter() - t0) / herhaal
    return (2 * n**3) / duur / 1e12


# --- eerst controleren dat we werkelijk in de stille stand staan -----------
# Anders meet je vol vermogen en noem je het stil. Zelfde les als bij de ijking.

kloks = {int(k) for k in smi("clocks.applications.graphics")}
if kloks != {WERKSTAND}:
    raise SystemExit(
        f"De kaarten staan op {kloks} MHz en niet op {WERKSTAND} MHz.\n"
        f"Zet ze eerst goed met:  ~/gpu stil"
    )

print("=" * 72)
print(f"Wat kost de stilte? — gemeten op {WERKSTAND} MHz")
print("=" * 72)
print()

# --- 1. Doorvoer per grootte ----------------------------------------------

print("--- Doorvoer, één kaart, fp32 ---")
print(f"{'matrix':>8} {'696 MHz':>12} {'vol vermogen':>14} {'verhouding':>12}")
verhoudingen = []
for n in GROOTTES:
    stil = doorvoer(n)
    vol = VOL_VERMOGEN[n]
    v = stil / vol
    verhoudingen.append(v)
    print(f"{n:>8} {stil:>9.2f} TF {vol:>11.2f} TF {v:>11.0%}")

gemiddeld = statistics.mean(verhoudingen)
print(f"\n  gemiddeld: {gemiddeld:.0%} van vol vermogen")
print()

# --- 2. Beide kaarten onder belasting -------------------------------------

print("--- Beide kaarten samen, 60 s ---")

stop = threading.Event()


def stook(kaart):
    a = torch.randn(8192, 8192, device=f"cuda:{kaart}")
    b = torch.randn(8192, 8192, device=f"cuda:{kaart}")
    while not stop.is_set():
        for _ in range(5):
            a @ b
        torch.cuda.synchronize(kaart)


draden = [threading.Thread(target=stook, args=(i,), daemon=True)
          for i in range(torch.cuda.device_count())]
for d in draden:
    d.start()

metingen = []
einde = time.time() + 60
while time.time() < einde:
    w = [float(x) for x in smi("power.draw")]
    t = [int(x) for x in smi("temperature.gpu")]
    metingen.append((w, t))
    print(f"\r  nog {int(einde - time.time()):2d} s   "
          + "   ".join(f"kaart {i}: {w[i]:5.1f} W {t[i]}°C" for i in range(len(w))),
          end="", flush=True)
    time.sleep(3)
stop.set()
print()
time.sleep(2)

tweede_helft = metingen[len(metingen) // 2:]
verbruik = [sum(m[0]) for m in tweede_helft]
temp = [max(m[1]) for m in tweede_helft]
print(f"\n  samen: {statistics.mean(verbruik):.0f} W")
print(f"  hoogste temperatuur: {max(temp)} °C")
print()

# --- 3. Wat kost determinisme? --------------------------------------------

print("--- De prijs van determinisme, fp32 bij 4096 ---")
torch.use_deterministic_algorithms(False)
torch.backends.cudnn.benchmark = True
los = statistics.median([doorvoer(4096) for _ in range(3)])

torch.use_deterministic_algorithms(True)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
vast = statistics.median([doorvoer(4096) for _ in range(3)])

print(f"  zonder determinisme: {los:.2f} TFLOPS")
print(f"  met determinisme:    {vast:.2f} TFLOPS")
print(f"  kosten:              {(1 - vast / los):.1%}")
print()

# --- wegschrijven ---------------------------------------------------------

verslag = "/home/arch/amber-werk/fase0/doorvoermeting.md"
with open(verslag, "w") as f:
    f.write("# Wat kost de stilte?\n\n")
    f.write(f"Gemeten op {WERKSTAND} MHz, de werkstand. Vergeleken met de\n")
    f.write("waarden bij de standaardklok van 8 aug 2026.\n\n")
    f.write("## Doorvoer, één kaart, fp32\n\n")
    f.write("| matrix | 696 MHz | vol vermogen | verhouding |\n|---:|---:|---:|---:|\n")
    for n, v in zip(GROOTTES, verhoudingen):
        f.write(f"| {n} | {v * VOL_VERMOGEN[n]:.2f} TF | "
                f"{VOL_VERMOGEN[n]:.2f} TF | {v:.0%} |\n")
    f.write(f"\n**Gemiddeld {gemiddeld:.0%} van vol vermogen.**\n\n")
    f.write("## Beide kaarten samen onder belasting\n\n")
    f.write(f"- verbruik samen: **{statistics.mean(verbruik):.0f} W**\n")
    f.write(f"- hoogste temperatuur: {max(temp)} °C\n\n")
    f.write("## De prijs van determinisme\n\n")
    f.write(f"fp32 bij matrix 4096: {los:.2f} TFLOPS zonder, {vast:.2f} met — "
            f"**{(1 - vast / los):.1%} kosten**.\n")
    f.flush()
    os.fsync(f.fileno())

print(f"Weggeschreven naar {verslag}")
