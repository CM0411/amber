"""De koeling van de P100 op de Z490 (28 aug 2026, kaartwissel).

De Tesla P100 heeft geen eigen ventilator; Cley zette er twee Noctua's op,
aan CHA_FAN2 en CHA_FAN4 van het bord. Het BIOS stuurt die naar de
processortemperatuur — nutteloos voor de kaart. Dit script leest elke paar
seconden de kaarttemperatuur (nvidia-smi) en zet de pwm-uitgangen van de
nct6779 naar de curve in koeling-p100.json. Dat bestand is van Cley: hij
past de curve aan, of zet `vast` op een percentage, zonder herstart.

Sinds 2 sep 2026 (X399) ook de processorfan: `cpu_kanaal` is haar
pwm-uitgang, `cpu_vast` een percentage of null. Bij null krijgt het BIOS
haar terug (pwm_enable 5 = de eigen curve van het bord). Onder
`cpu_minimum` gaat ze nooit, en wordt de processor te heet dan gaat ze
naar 100% wat er ook is ingesteld.

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
CHIP = "nct6779"
CPU_HEET = 65        # Tdie in graden (AMD noemt 68 als grens voor de 1920X); daarboven de processorfan altijd vol
STANDAARD = {"kanalen": [1, 2, 4, 6], "curve": [[40, 35], [78, 100]], "vast": None,
             "vermogen_w": None, "klok_mhz": None, "elke_s": 3,
             "cpu_kanaal": None, "cpu_vast": None, "cpu_minimum": 30}


def hwmon(chip=CHIP):
    for naam in os.listdir("/sys/class/hwmon"):
        pad = os.path.join("/sys/class/hwmon", naam)
        try:
            if open(os.path.join(pad, "name")).read().strip() == chip:
                return pad
        except OSError:
            pass
    if chip == CHIP:
        raise SystemExit(f"geen {CHIP} onder /sys/class/hwmon")
    return None


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
        schrijf("instelling gelezen: kanalen %s, curve %s, vast %s, vermogen %s W, klok %s, cpu-fan %s"
                % (nieuw.get("kanalen"), nieuw.get("curve"), nieuw.get("vast"), nieuw.get("vermogen_w"),
                   nieuw.get("klok_mhz"), "BIOS" if nieuw.get("cpu_vast") is None else f"{nieuw.get('cpu_vast')}%"))
        return nieuw
    except Exception as e:
        schrijf(f"instelling onleesbaar ({e}) — de vorige blijft gelden")
        return vorige


def temperatuur():
    try:
        uit = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10)
        # de heetste kaart telt (1 sep 2026, tweede P100 in de Z490):
        # beide kaarten hangen aan dezelfde luchtstroom, dus de curve
        # volgt de warmste van de twee
        return max(int(r) for r in uit.stdout.strip().splitlines() if r.strip())
    except Exception:
        return None


def cpu_temperatuur():
    """Tdie van k10temp, de heetste van de twee dies van de Threadripper (2 sep 2026).
    Tctl ligt op dit bord 27 graden hoger dan Tdie (een vaste opslag van AMD,
    bedoeld voor de BIOS-curve); Tdie is de echte temperatuur."""
    hoogste = None
    for naam in os.listdir("/sys/class/hwmon"):
        pad = os.path.join("/sys/class/hwmon", naam)
        try:
            if open(os.path.join(pad, "name")).read().strip() != "k10temp":
                continue
            t = None
            for n in (1, 2, 3):
                try:
                    if open(os.path.join(pad, f"temp{n}_label")).read().strip() == "Tdie":
                        t = int(open(os.path.join(pad, f"temp{n}_input")).read()) / 1000
                        break
                except OSError:
                    pass
            if t is None:
                t = int(open(os.path.join(pad, "temp1_input")).read()) / 1000 - 27
            hoogste = t if hoogste is None else max(hoogste, t)
        except OSError:
            pass
    return hoogste


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


def cpu_bios(pad, k):
    """De processorfan terug aan het BIOS geven (enable 5 = de curve van het bord)."""
    try:
        with open(f"{pad}/pwm{k}_enable", "w") as f:
            f.write("5")
    except OSError as e:
        schrijf(f"cpu-kanaal {k} niet aan het BIOS terug te geven: {e}")


def cpu_regel(pad, inst, stand, cpu_t):
    """Elke ronde: null = BIOS, anders het vaste percentage; te heet = vol."""
    k = inst.get("cpu_kanaal")
    if not k:
        return
    wens = inst.get("cpu_vast")
    if cpu_t is not None and cpu_t >= CPU_HEET:
        wens = 100
    if wens is None:
        if stand.get("cpu") != "bios":
            cpu_bios(pad, k)
            stand["cpu"] = "bios"
            schrijf("cpu-fan: terug naar het BIOS")
        return
    wens = max(float(inst.get("cpu_minimum") or 30), min(100.0, float(wens)))
    if stand.get("cpu") != wens:
        zet(pad, [k], wens)
        stand["cpu"] = wens
        schrijf(f"cpu-fan: {wens:.0f}%" + (" (processor te heet)" if cpu_t is not None and cpu_t >= CPU_HEET else ""))


def aantal_kaarten():
    try:
        uit = subprocess.run(["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10)
        return max(1, len([r for r in uit.stdout.splitlines() if r.strip()]))
    except Exception:
        return 1


def sleutel(naam, i):
    """instellingsnaam per kaart: kaart 0 houdt de oude naam, kaart 1 krijgt _1 (1 sep 2026)"""
    return naam if i == 0 else f"{naam}_{i}"


def vermogen(w, stand, i=0):
    if w is None or stand.get(("vermogen", i)) == w:
        return
    r = subprocess.run(["nvidia-smi", "-i", str(i), "-pl", str(int(w))], capture_output=True, text=True)
    stand[("vermogen", i)] = w
    tekst = (r.stdout or r.stderr).strip().splitlines()
    schrijf(f"kaart {i}: vermogensplafond {w} W: {tekst[-1] if tekst else 'gezet'}")


def klok(mhz, stand, i=0):
    """Vaste klok of vrij; alleen bij verandering. Pascal kent geen -lgc,
    wel application clocks (-ac geheugen,grafisch) — en de auto-boost moet
    dan uit, anders klimt de kaart er toch overheen. Per kaart (1 sep 2026)."""
    if stand.get(("klok", i), "onbekend") == mhz:
        return
    if mhz is None:
        subprocess.run(["nvidia-smi", "-i", str(i), "-rac"], capture_output=True, text=True)
        r = subprocess.run(["nvidia-smi", "-i", str(i), "--auto-boost-default=ENABLED"], capture_output=True, text=True)
    else:
        subprocess.run(["nvidia-smi", "-i", str(i), "--auto-boost-default=DISABLED"], capture_output=True, text=True)
        r = subprocess.run(["nvidia-smi", "-i", str(i), "-ac", f"715,{int(mhz)}"], capture_output=True, text=True)
    stand[("klok", i)] = mhz
    tekst = (r.stdout or r.stderr).strip().splitlines()
    schrijf(f"kaart {i}: klok {'vrij' if mhz is None else str(int(mhz)) + ' MHz'}: {tekst[-1] if tekst else 'gezet'}")


def main():
    pad = hwmon()
    stand = {}
    inst = lees_instelling(dict(STANDAARD), stand)
    huidig = 100.0
    zet(pad, inst["kanalen"], huidig)
    schrijf(f"gestart — fans op 100% tot de eerste meting ({pad})")

    def stop(*_):
        zet(pad, inst["kanalen"], 100)
        if inst.get("cpu_kanaal"):
            cpu_bios(pad, inst["cpu_kanaal"])
        schrijf("gestopt — fans op 100% achtergelaten, cpu-fan terug aan het BIOS")
        sys.exit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    laatst_gelogd = 0
    while True:
        vers = lees_instelling(inst, stand)
        if vers is not inst:          # nieuw bestand: de huidige stand meteen op de (nieuwe) kanalen zetten
            inst = vers
            zet(pad, inst["kanalen"], huidig)
            stand.pop("cpu", None)
        for i in range(aantal_kaarten()):
            vermogen(inst.get(sleutel("vermogen_w", i)), stand, i)
            klok(inst.get(sleutel("klok_mhz", i)), stand, i)
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
        cpu_t = cpu_temperatuur()
        cpu_regel(pad, inst, stand, cpu_t)
        nu = time.time()
        if nu - laatst_gelogd >= 300 or (t is not None and t >= 78) or (cpu_t is not None and cpu_t >= CPU_HEET):
            cpu_tekst = "BIOS" if stand.get("cpu") in (None, "bios") else f"{stand['cpu']:.0f}%"
            schrijf(f"kaart {t if t is not None else '?'} °C → fans {huidig:.0f}%; "
                    f"processor {cpu_t if cpu_t is not None else '?'} °C → cpu-fan {cpu_tekst}")
            laatst_gelogd = nu
        time.sleep(float(inst.get("elke_s", 3)))


if __name__ == "__main__":
    main()
