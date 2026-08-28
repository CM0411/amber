"""De koeling van de P100 op de Z490 (28 aug 2026, kaartwissel).

De Tesla P100 heeft geen eigen ventilator; Cley zette er twee Noctua's op,
aan CHA_FAN2 en CHA_FAN4 van het bord. Het BIOS stuurt die naar de
processortemperatuur — nutteloos voor de kaart. Dit script leest elke paar
seconden de kaarttemperatuur (nvidia-smi) en zet de pwm-uitgangen van de
nct6798 naar de curve in koeling-p100.json. Dat bestand is van Cley: hij
past de curve aan, of zet `vast` op een percentage, zonder herstart.

Veilig bij twijfel: kan de temperatuur niet gelezen worden, of stopt dit
script, dan gaan de fans naar 100%. Omhoog gaat meteen, omlaag langzaam
(hoogstens 5 procentpunt per ronde) — geen gejank. Draait als root
(amber-koeling-p100.service), want /sys/class/hwmon is alleen-lezen voor arch.
"""
import json
import os
import signal
import subprocess
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
INSTELLING = os.path.join(HIER, "koeling-p100.json")
LOG = os.path.join(HIER, "koeling-p100.log")
CHIP = "nct6798"
STANDAARD = {"kanalen": [1, 2, 4, 6], "curve": [[40, 35], [78, 100]], "vast": None,
             "vermogen_w": None, "klok_mhz": None, "elke_s": 3}


def hwmon():
    for naam in os.listdir("/sys/class/hwmon"):
        pad = os.path.join("/sys/class/hwmon", naam)
        try:
            if open(os.path.join(pad, "name")).read().strip() == CHIP:
                return pad
        except OSError:
            pass
    raise SystemExit(f"geen {CHIP} onder /sys/class/hwmon")


def schrijf(tekst):
    regel = f"{time.strftime('%d-%m %H:%M:%S')}  {tekst}"
    print(regel, flush=True)
    try:
        with open(LOG, "a") as f:
            f.write(regel + "\n")
    except OSError:
        pass


def lees_instelling(vorige, stand):
    """Het bestand van Cley; alleen opnieuw lezen als het veranderd is."""
    try:
        mt = os.stat(INSTELLING).st_mtime
        if stand.get("mtime") == mt:
            return vorige
        with open(INSTELLING) as f:
            nieuw = json.load(f)
        stand["mtime"] = mt
        schrijf("instelling gelezen: kanalen %s, curve %s, vast %s, vermogen %s W, klok %s"
                % (nieuw.get("kanalen"), nieuw.get("curve"), nieuw.get("vast"), nieuw.get("vermogen_w"), nieuw.get("klok_mhz")))
        return nieuw
    except Exception as e:
        schrijf(f"instelling onleesbaar ({e}) — de vorige blijft gelden")
        return vorige


def temperatuur():
    try:
        uit = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10)
        return int(uit.stdout.strip().splitlines()[0])
    except Exception:
        return None


def curve_procent(curve, t):
    punten = sorted((float(g), float(p)) for g, p in curve)
    if t <= punten[0][0]:
        return punten[0][1]
    for (g0, p0), (g1, p1) in zip(punten, punten[1:]):
        if t <= g1:
            return p0 + (p1 - p0) * (t - g0) / (g1 - g0)
    return 100.0


def zet(pad, kanalen, procent):
    pwm = max(0, min(255, round(procent * 255 / 100)))
    for k in kanalen:
        try:
            with open(f"{pad}/pwm{k}_enable", "w") as f:
                f.write("1")
            with open(f"{pad}/pwm{k}", "w") as f:
                f.write(str(pwm))
        except OSError as e:
            schrijf(f"kanaal {k} niet te zetten: {e}")


def vermogen(w, stand):
    if w is None or stand.get("vermogen") == w:
        return
    r = subprocess.run(["nvidia-smi", "-pl", str(int(w))], capture_output=True, text=True)
    stand["vermogen"] = w
    tekst = (r.stdout or r.stderr).strip().splitlines()
    schrijf(f"vermogensplafond {w} W: {tekst[-1] if tekst else 'gezet'}")


def klok(mhz, stand):
    """Vaste klok of vrij; alleen bij verandering. Pascal kent geen -lgc,
    wel application clocks (-ac geheugen,grafisch) — en de auto-boost moet
    dan uit, anders klimt de kaart er toch overheen."""
    if stand.get("klok", "onbekend") == mhz:
        return
    if mhz is None:
        subprocess.run(["nvidia-smi", "-rac"], capture_output=True, text=True)
        r = subprocess.run(["nvidia-smi", "--auto-boost-default=ENABLED"], capture_output=True, text=True)
    else:
        subprocess.run(["nvidia-smi", "--auto-boost-default=DISABLED"], capture_output=True, text=True)
        r = subprocess.run(["nvidia-smi", "-ac", f"715,{int(mhz)}"], capture_output=True, text=True)
    stand["klok"] = mhz
    tekst = (r.stdout or r.stderr).strip().splitlines()
    schrijf(f"klok {'vrij' if mhz is None else str(int(mhz)) + ' MHz'}: {tekst[-1] if tekst else 'gezet'}")


def main():
    pad = hwmon()
    stand = {}
    inst = lees_instelling(dict(STANDAARD), stand)
    huidig = 100.0
    zet(pad, inst["kanalen"], huidig)
    schrijf(f"gestart — fans op 100% tot de eerste meting ({pad})")

    def stop(*_):
        zet(pad, inst["kanalen"], 100)
        schrijf("gestopt — fans op 100% achtergelaten")
        sys.exit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    laatst_gelogd = 0
    while True:
        vers = lees_instelling(inst, stand)
        if vers is not inst:          # nieuw bestand: de huidige stand meteen op de (nieuwe) kanalen zetten
            inst = vers
            zet(pad, inst["kanalen"], huidig)
        vermogen(inst.get("vermogen_w"), stand)
        klok(inst.get("klok_mhz"), stand)
        t = temperatuur()
        if t is None:
            doel = 100.0
        elif inst.get("vast") is not None:
            doel = float(inst["vast"])
        else:
            doel = curve_procent(inst["curve"], t)
        nieuw = doel if doel >= huidig else max(doel, huidig - 5)
        if abs(nieuw - huidig) >= 0.5:
            zet(pad, inst["kanalen"], nieuw)
        huidig = nieuw
        nu = time.time()
        if nu - laatst_gelogd >= 300 or (t is not None and t >= 78):
            schrijf(f"kaart {t if t is not None else '?'} °C → fans {huidig:.0f}%")
            laatst_gelogd = nu
        time.sleep(float(inst.get("elke_s", 3)))


if __name__ == "__main__":
    main()
