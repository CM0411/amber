"""De hartkamer — Claudes eigen venster op Amber (31 aug 2026, Cleys
opdracht: "naar eigen smaak, vanaf nul"). Poort 8030, één pagina, alles
in eigen stijl.

De levende gegevens komen van het venster op poort 8000 (zelfde machine);
deze server geeft ze door zodat de browser nergens anders heen hoeft —
ook haar stem-wavs, met Range-steun want Safari vraagt audio in stukjes.
Raakt niets aan: alleen lezen en doorgeven.
"""
import json
import subprocess
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import sys
MAP = "/home/arch/amber-werk/hartkamer"
# poort en pagina als argumenten (2 sep 2026): dezelfde server geeft op 8030 de
# grote hartkamer en op 8031 de telefoon-versie; beide lezen hetzelfde venster
POORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8030
PAGINA = sys.argv[2] if len(sys.argv) > 2 else "hartkamer.html"
# wat doorgegeven mag worden (voorvoegsels op het venster van poort 8000)
DOORGEEF = ("/stand.json", "/amber-zegt.json", "/gesprek.json",
            "/gesprek-zeg", "/zoek", "/voorstellen.json",
            "/voorstel-besluit", "/vraag-stel", "/vraag-antwoord.json",
            "/rapport/", "/ik-kijk")


class Hartkamer(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _stuur(self, inhoud, soort="text/html; charset=utf-8"):
        self.send_response(200)
        self.send_header("Content-Type", soort)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(inhoud)

    def do_GET(self):
        if self.path.startswith("/kaarten.json"):
            # beide P100's, rechtstreeks van nvidia-smi (1 sep 2026)
            try:
                uit = subprocess.run(["nvidia-smi", "--query-gpu=index,temperature.gpu,power.draw,memory.used,utilization.gpu",
                                      "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=8)
                kaarten = []
                for r in uit.stdout.strip().splitlines():
                    i, t, w, v, u = [x.strip() for x in r.split(",")]
                    kaarten.append({"index": int(i), "temp": int(t), "watt": float(w), "vram": int(v), "util": int(u)})
                self._stuur(json.dumps(kaarten).encode(), "application/json")
            except Exception:
                self._stuur(b"[]", "application/json")
            return
        if self.path.startswith("/uren.json"):
            # onze uren, gemeten uit de sessieverslagen (1 sep 2026)
            try:
                with open("/home/arch/amber/uren-gemeten.json", "rb") as f:
                    self._stuur(f.read(), "application/json")
            except OSError:
                self._stuur(b"{}", "application/json")
            return
        if self.path.startswith(DOORGEEF):
            verzoek = urllib.request.Request(
                f"http://127.0.0.1:8000{self.path}")
            bereik = self.headers.get("Range")
            if bereik:
                verzoek.add_header("Range", bereik)
            try:
                with urllib.request.urlopen(verzoek, timeout=8) as f:
                    inhoud = f.read()
                    self.send_response(f.status)
                    for kop in ("Content-Type", "Content-Range",
                                "Accept-Ranges"):
                        w = f.headers.get(kop)
                        if w:
                            self.send_header(kop, w)
                    self.send_header("Content-Length", str(len(inhoud)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(inhoud)
            except Exception:
                self._stuur(b"{}", "application/json")
            return
        try:
            with open(f"{MAP}/{PAGINA}", "rb") as f:
                self._stuur(f.read())
        except OSError:
            self._stuur(b"<p>de hartkamer is er even niet</p>")


ThreadingHTTPServer(("0.0.0.0", POORT), Hartkamer).serve_forever()
