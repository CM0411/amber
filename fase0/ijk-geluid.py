"""
Fase 0 — ijken hoe luid de machine wordt per vermogensstand.

Beide kaarten tegelijk belasten, van zacht naar hard, en na elke stap wachten
op Cley's oordeel. De uitkomst bepaalt Ambers dagindeling: bij welke stand kan
ze werken terwijl er iemand in de kamer zit.

De kaarten accepteren geen vermogenslimiet onder 125 W. Om daaronder te komen
wordt de rekenklok vastgezet; 544 MHz is de laagste die ze ondersteunen.

Let op: dat gaat op Pascal met `-ac` (application clocks), niet met `-lgc` —
dat laatste bestaat pas vanaf Volta en wordt hier geweigerd. De geheugenklok
ligt vast op 715 MHz; alleen de rekenklok is instelbaar.

Draaien (root nodig voor nvidia-smi -pl en -ac):

    sudo /home/arch/amber-werk/venv/bin/python /home/arch/amber-werk/fase0/ijk-geluid.py

Afbreken mag altijd met Ctrl-C — de kaarten worden dan teruggezet.
Hervatten na een pauze: dezelfde regel met een beginstap erachter, bijvoorbeeld

    sudo ... ijk-geluid.py 4
"""

import os
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import subprocess
import sys
import threading
import time
from datetime import datetime

import torch

VERSLAG = "/home/arch/amber-werk/fase0/geluidsmeting.md"
SECONDEN = 180          # per stap; ventilatoren reageren traag, dus niet korter
AANTAL_KAARTEN = torch.cuda.device_count()

# (label, soort, waarde). "klok" zet de kloksnelheid vast, "vermogen" de limiet.
STAPPEN = [
    # Alleen exacte waarden uit de lijst van de kaart werken. nvidia-smi weigert
    # de rest zonder foutcode, en dan meet je stilzwijgend de vorige stap opnieuw.
    #   nvidia-smi -q -d SUPPORTED_CLOCKS
    ("544 MHz vastgezet  (het laagste dat de kaart kan)", "klok", 544),
    ("696 MHz vastgezet", "klok", 696),
    ("898 MHz vastgezet", "klok", 898),
    ("125 W  (de laagste vermogenslimiet)",               "vermogen", 125),
    ("150 W",                                             "vermogen", 150),
    ("175 W",                                             "vermogen", 175),
    ("200 W",                                             "vermogen", 200),
    ("250 W  (vol vermogen — dit klonk al als een straaljager)", "vermogen", 250),
]


def smi(*args):
    return subprocess.run(["nvidia-smi", *args], capture_output=True, text=True)


def zet_stand(soort, waarde):
    """Zet alle kaarten in de gevraagde stand."""
    for i in range(AANTAL_KAARTEN):
        if soort == "klok":
            # Vermogenslimiet terug naar vol, anders knijpen twee grenzen tegelijk
            # en weet je achteraf niet welke de begrenzing was.
            smi("-i", str(i), "-pl", "250")
            r = smi("-i", str(i), "-ac", f"715,{waarde}")
        else:
            smi("-i", str(i), "-rac")          # klok weer vrijgeven
            r = smi("-i", str(i), "-pl", str(waarde))
        if r.returncode != 0:
            print(f"  ! kaart {i}: {r.stderr.strip() or r.stdout.strip()}")

    # Lezen wat er werkelijk staat. nvidia-smi meldt een geweigerde klok als
    # waarschuwing en geeft gewoon 0 terug; zonder deze controle meet je dan
    # stilzwijgend de vórige stap nog een keer.
    if soort == "klok":
        r = smi("--query-gpu=index,clocks.applications.graphics",
                "--format=csv,noheader,nounits")
        for regel in r.stdout.strip().splitlines():
            nr, gezet = [x.strip() for x in regel.split(",")]
            if int(gezet) != waarde:
                print(f"\n  ! GESTOPT: kaart {nr} staat op {gezet} MHz en niet op "
                      f"{waarde} MHz.\n    Waarschijnlijk geen ondersteunde waarde — "
                      f"kijk met: nvidia-smi -q -d SUPPORTED_CLOCKS")
                raise SystemExit(1)


def herstel():
    print("\nKaarten terugzetten naar de standaardstand...")
    for i in range(AANTAL_KAARTEN):
        smi("-i", str(i), "-rac")
        smi("-i", str(i), "-pl", "250")
    print("Gedaan.")


def belast(stop):
    """Eén draad per kaart, aanhoudend matmul tot het stopsein komt."""
    def werker(dev):
        a = torch.randn(8192, 8192, device=f"cuda:{dev}")
        b = torch.randn(8192, 8192, device=f"cuda:{dev}")
        while not stop.is_set():
            for _ in range(10):
                a @ b
            torch.cuda.synchronize(dev)     # wachten, anders stapelt de wachtrij op

    draden = [threading.Thread(target=werker, args=(i,), daemon=True)
              for i in range(AANTAL_KAARTEN)]
    for d in draden:
        d.start()
    return draden


def bemonster(seconden, stop):
    """Elke twee seconden meten. Geeft de gemiddelden over de laatste helft terug,
    want de eerste helft is opwarmen en zegt niets over de eindstand."""
    metingen = []
    einde = time.time() + seconden
    while time.time() < einde and not stop.is_set():
        r = smi("--query-gpu=index,power.draw,temperature.gpu,clocks.sm",
                "--format=csv,noheader,nounits")
        rij = []
        for regel in r.stdout.strip().splitlines():
            d = [x.strip() for x in regel.split(",")]
            if len(d) == 4:
                rij.append((int(d[0]), float(d[1]), int(d[2]), int(d[3])))
        if rij:
            metingen.append(rij)
        resterend = int(einde - time.time())
        print(f"\r  belasten... nog {resterend:3d} s   "
              + "   ".join(f"kaart {k}: {w:5.1f} W  {t}°C  {c} MHz" for k, w, t, c in rij),
              end="", flush=True)
        time.sleep(2)
    print()

    tweede_helft = metingen[len(metingen) // 2:] or metingen
    samenvatting = []
    for i in range(AANTAL_KAARTEN):
        w = [r[i][1] for r in tweede_helft if len(r) > i]
        t = [r[i][2] for r in tweede_helft if len(r) > i]
        c = [r[i][3] for r in tweede_helft if len(r) > i]
        if w:
            samenvatting.append((i, sum(w) / len(w), max(t), sum(c) // len(c)))
    return samenvatting


def schrijf(regel):
    nieuw = not os.path.exists(VERSLAG)
    with open(VERSLAG, "a") as f:
        if nieuw:
            f.write("# Geluidsmeting — fase 0\n\n")
            f.write("Beide kaarten tegelijk belast, 180 s per stap. "
                    "Het oordeel is van Cley, die naast de server zit.\n\n")
            f.write("| stap | stand | verbruik samen | temp | klok | oordeel |\n")
            f.write("|---|---|---:|---:|---:|---|\n")
        f.write(regel + "\n")
        f.flush()
        os.fsync(f.fileno())


def main():
    begin = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    print("=" * 72)
    print("Geluidsijking — beide kaarten tegelijk")
    print("=" * 72)
    print(f"{AANTAL_KAARTEN} kaarten, {SECONDEN} s per stap, beginnend bij stap {begin}.")
    print("Na elke stap wordt gewacht op jouw oordeel. Typ 'stop' om te pauzeren;")
    print(f"hervatten kan later met het stapnummer erachter. Verslag: {VERSLAG}")
    print()

    for i in range(AANTAL_KAARTEN):
        smi("-i", str(i), "-pm", "1")     # standen vasthouden ook zonder proces

    try:
        for nr, (label, soort, waarde) in enumerate(STAPPEN, start=1):
            if nr < begin:
                continue

            print("-" * 72)
            print(f"STAP {nr} van {len(STAPPEN)}:  {label}")
            print("-" * 72)
            zet_stand(soort, waarde)
            time.sleep(2)

            stop = threading.Event()
            belast(stop)
            samenvatting = bemonster(SECONDEN, stop)
            stop.set()
            time.sleep(3)                  # draden laten uitlopen

            totaal = sum(s[1] for s in samenvatting)
            temp = max((s[2] for s in samenvatting), default=0)
            klok = max((s[3] for s in samenvatting), default=0)
            print(f"\n  gemeten: {totaal:.0f} W samen, "
                  f"hoogste temperatuur {temp} °C, klok {klok} MHz")
            print()
            print("  Hoe klinkt hij? Bijvoorbeeld: stil / zacht hoorbaar / duidelijk")
            print("  hoorbaar / hinderlijk / te hard.  ('stop' = pauzeren)")
            oordeel = input("  > ").strip()

            schrijf(f"| {nr} | {label} | {totaal:.0f} W | {temp} °C | {klok} MHz | "
                    f"{oordeel or '—'} |")

            if oordeel.lower() in ("stop", "pauze", "q"):
                print(f"\nGepauzeerd. Hervatten met:  "
                      f"sudo {sys.executable} {os.path.abspath(__file__)} {nr + 1}")
                break
        else:
            print("\nAlle stappen gedaan.")
    except KeyboardInterrupt:
        print("\n\nAfgebroken.")
    finally:
        herstel()
        print(f"\nVerslag staat in {VERSLAG}")
        print(f"Gemeten op {datetime.now().strftime('%d-%m-%Y %H:%M')}")


if __name__ == "__main__":
    main()
