"""Het koelingspaneel van de P100 (28 aug 2026): een pagina met schuiven.

Draait als arch op poort 8010 en doet twee dingen: de stand tonen (kaart,
vermogen, klok, wat er op de pwm-uitgangen staat) en koeling-p100.json
bijwerken. Het regelen zelf doet koeling-p100.py (als root); dit paneel
raakt de hardware niet aan, het schrijft alleen het instellingenbestand.
Sinds 2 sep 2026 ook de processorfan (cpu_vast) en haar toerental.
"""
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HIER = os.path.dirname(os.path.abspath(__file__))
INSTELLING = os.path.join(HIER, "koeling-p100.json")
PAGINA = os.path.join(HIER, "koeling.html")
POORT = 8010
VELDEN = {"vast": (0, 100), "vermogen_w": (125, 250), "klok_mhz": (544, 1328),
          "vermogen_w_1": (125, 250), "klok_mhz_1": (544, 1328),
          "cpu_vast": (30, 100)}


def hwmon(chip="nct6779"):
    for naam in os.listdir("/sys/class/hwmon"):
        pad = os.path.join("/sys/class/hwmon", naam)
        try:
            if open(os.path.join(pad, "name")).read().strip() == chip:
                return pad
        except OSError:
            pass
    return None


def lees_int(pad):
    try:
        return int(open(pad).read())
    except (OSError, ValueError):
        return None


def cpu_temperatuur():
    hoogste = None
    for naam in os.listdir("/sys/class/hwmon"):
        pad = os.path.join("/sys/class/hwmon", naam)
        try:
            if open(os.path.join(pad, "name")).read().strip() != "k10temp":
                continue
        except OSError:
            continue
        # Tdie is de echte temperatuur; Tctl ligt er op dit bord 27 graden boven (2 sep 2026)
        t = None
        for n in (1, 2, 3):
            try:
                if open(os.path.join(pad, f"temp{n}_label")).read().strip() == "Tdie":
                    t = lees_int(os.path.join(pad, f"temp{n}_input"))
                    break
            except OSError:
                pass
        if t is None:
            t = lees_int(os.path.join(pad, "temp1_input"))
            t = None if t is None else t - 27000
        if t is not None:
            hoogste = t if hoogste is None else max(hoogste, t)
    return None if hoogste is None else round(hoogste / 1000)


def kaart():
    try:
        uit = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,power.draw,clocks.sm",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        # alle kaarten (1 sep 2026, tweede P100): de eerste blijft de
        # hoofdwaarde voor het paneel, de rest komt mee als lijst
        rijen = [[x.strip() for x in r.split(",")] for r in uit.stdout.strip().splitlines() if r.strip()]
        kaarten = [(int(t), float(w), int(mhz)) for t, w, mhz in rijen]
        kaart.alle = kaarten
        return kaarten[0]
    except Exception:
        kaart.alle = []
        return None, None, None


def stand():
    with open(INSTELLING) as f:
        inst = json.load(f)
    t, w, mhz = kaart()
    pad = hwmon()
    pwm, rpm = [], []
    cpu = {"temp": cpu_temperatuur(), "pwm": None, "rpm": None, "bios": None}
    if pad:
        for k in inst.get("kanalen", []):
            pwm.append(lees_int(f"{pad}/pwm{k}") or 0)
            rpm.append(lees_int(f"{pad}/fan{k}_input"))
        k = inst.get("cpu_kanaal")
        if k:
            cpu["pwm"] = lees_int(f"{pad}/pwm{k}")
            cpu["rpm"] = lees_int(f"{pad}/fan{k}_input")
            cpu["bios"] = lees_int(f"{pad}/pwm{k}_enable") == 5   # 0 = vol (pwm 255), 1 = handmatig, 5 = de curve van het bord
    fans = round(max(pwm) * 100 / 255) if pwm else None
    return {"temp": t, "watt": w, "mhz": mhz, "pwm": pwm, "rpm": rpm, "fans": fans, "cpu": cpu,
            "kaarten": [{"temp": a, "watt": b, "mhz": c} for a, b, c in getattr(kaart, "alle", [])],
            "instelling": {k: inst.get(k) for k in ("vast", "vermogen_w", "klok_mhz", "vermogen_w_1", "klok_mhz_1",
                                                    "curve", "kanalen", "cpu_kanaal", "cpu_vast", "cpu_minimum")}}


def bijwerken(veld):
    with open(INSTELLING) as f:
        inst = json.load(f)
    for k, v in veld.items():
        if k not in VELDEN:
            continue
        if v is None:
            inst[k] = None
        else:
            lo, hi = VELDEN[k]
            inst[k] = max(lo, min(hi, int(v)))
    tmp = INSTELLING + ".tmp"
    with open(tmp, "w") as f:
        json.dump(inst, f, indent=2, ensure_ascii=False)
    os.replace(tmp, INSTELLING)
    return inst


class Paneel(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith("/stand"):
            return self._json(stand())
        with open(PAGINA, "rb") as f:
            raw = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if not self.path.startswith("/instelling"):
            return self._json({"fout": "onbekend pad"}, 404)
        n = int(self.headers.get("Content-Length", "0"))
        try:
            veld = json.loads(self.rfile.read(n) or b"{}")
            return self._json({"ok": True, "instelling": bijwerken(veld)})
        except Exception as e:
            return self._json({"fout": str(e)}, 400)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", POORT), Paneel).serve_forever()
