"""Het koelingspaneel van de P100 (28 aug 2026): een pagina met schuiven.

Draait als arch op poort 8010 en doet twee dingen: de stand tonen (kaart,
vermogen, klok, wat er op de pwm-uitgangen staat) en koeling-p100.json
bijwerken. Het regelen zelf doet koeling-p100.py (als root); dit paneel
raakt de hardware niet aan, het schrijft alleen het instellingenbestand.
"""
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HIER = os.path.dirname(os.path.abspath(__file__))
INSTELLING = os.path.join(HIER, "koeling-p100.json")
PAGINA = os.path.join(HIER, "koeling.html")
POORT = 8010
VELDEN = {"vast": (0, 100), "vermogen_w": (125, 250), "klok_mhz": (544, 1328)}


def hwmon():
    for naam in os.listdir("/sys/class/hwmon"):
        pad = os.path.join("/sys/class/hwmon", naam)
        try:
            if open(os.path.join(pad, "name")).read().strip() == "nct6798":
                return pad
        except OSError:
            pass
    return None


def kaart():
    try:
        uit = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,power.draw,clocks.sm",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        t, w, mhz = [x.strip() for x in uit.stdout.strip().splitlines()[0].split(",")]
        return int(t), float(w), int(mhz)
    except Exception:
        return None, None, None


def stand():
    with open(INSTELLING) as f:
        inst = json.load(f)
    t, w, mhz = kaart()
    pad = hwmon()
    pwm = []
    if pad:
        for k in inst.get("kanalen", []):
            try:
                pwm.append(int(open(f"{pad}/pwm{k}").read()))
            except OSError:
                pwm.append(0)
    fans = round(max(pwm) * 100 / 255) if pwm else None
    return {"temp": t, "watt": w, "mhz": mhz, "pwm": pwm, "fans": fans,
            "instelling": {k: inst.get(k) for k in ("vast", "vermogen_w", "klok_mhz", "curve", "kanalen")}}


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
