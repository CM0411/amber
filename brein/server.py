"""Het brein-venster: webserver op de DL380, zoals de roadmap voorschrijft.

  /            de levende pagina — cirkel, lagen, wat ze nu doet
  /stand.json  de gegevens erachter (kijker + stand van de grote run)
  /rapport     het laatste nachtrapport
"""
import json, os, re, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAP = "/home/arch/amber-werk/brein"

# Het wachtwoord van de rekenmachine staat búiten de repo — een repo die ooit
# openbaar wordt mag nooit een geheim in zijn geschiedenis dragen.
def _geheim():
    with open("/home/arch/.amber-geheim") as f:
        return f.read().strip()
X399 = "arch@192.168.1.170"

_run = {"regel": "", "proefwerk": "", "tijd": 0.0}
_slot = threading.Lock()


def _ververs_run():
    while True:
        r = subprocess.run(
            ["sshpass", "-p", _geheim(), "ssh", "-o", "ConnectTimeout=6", X399,
             "grep -E 'ms/st' ~/leven.log | tail -1; "
             "grep -E '^  stap +[0-9]+ \\|' ~/leven.log | tail -1; "
             "echo ===; grep 'wereld open' ~/leven.log | tail -15; "
             "echo ===; grep -E '^  stap +[0-9]+ \\|' ~/leven.log | tail -400"],
            capture_output=True, text=True)
        if r.returncode == 0:
            ruw = r.stdout.split("===")
            regels = [x for x in ruw[0].strip().splitlines() if x.strip()]
            # de rand van haar wereld, per familie, uit de doorbraakregels
            wereld = {"rekenen": 2, "puzzel": 2, "code": 2}
            doorbraken = []
            for regel in (ruw[1].splitlines() if len(ruw) > 1 else []):
                m = re.search(r"stap\s+(\d+) \| wereld open: (\w+) tot (\d+)", regel)
                if m:
                    stap, fam, tot = int(m.group(1)), m.group(2), int(m.group(3))
                    wereld[fam] = max(wereld.get(fam, 2), tot)
                    doorbraken.append({"stap": stap, "familie": fam, "tot": tot})
            curve = []
            for regel in (ruw[2].splitlines() if len(ruw) > 2 else []):
                m = re.search(r"stap +(\d+) \|.*ladder +(\d+)%", regel)
                if m:
                    stap, pct = int(m.group(1)), int(m.group(2))
                    # herstart-nulmetingen heten "stap 0" — alleen de echte
                    # oplopende lijn houden
                    if not curve or stap > curve[-1][0]:
                        curve.append([stap, pct])
            with _slot:
                _run["regel"] = regels[0].strip() if regels else ""
                _run["proefwerk"] = regels[1].strip() if len(regels) > 1 else ""
                _run["wereld"] = wereld
                _run["doorbraken"] = doorbraken[-4:]
                _run["curve"] = curve
                _run["tijd"] = time.time()
        time.sleep(5)


class Venster(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _stuur(self, inhoud, soort="text/html; charset=utf-8"):
        self.send_response(200)
        self.send_header("Content-Type", soort)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(inhoud)

    def do_PUT(self):
        # /upload?naam=bestand — de sleep-pagina stuurt bestanden hierheen.
        # Gebouwd omdat kopiëren uit de chat en overtypen allebei ellende
        # waren; slepen in de browser werkt vanaf elk apparaat.
        if not self.path.startswith("/upload"):
            self.send_response(404); self.end_headers(); return
        from urllib.parse import urlparse, parse_qs, unquote
        q = parse_qs(urlparse(self.path).query)
        naam = os.path.basename(unquote(q.get("naam", ["bestand"])[0]))
        lengte = int(self.headers.get("Content-Length", 0))
        if not naam or lengte <= 0 or lengte > 4_000_000_000:
            self.send_response(400); self.end_headers(); return
        doel = os.path.join("/home/arch/inbox", naam)
        with open(doel + ".deel", "wb") as f:
            over = lengte
            while over > 0:
                stuk = self.rfile.read(min(1 << 20, over))
                if not stuk:
                    break
                f.write(stuk); over -= len(stuk)
            f.flush(); os.fsync(f.fileno())
        os.replace(doel + ".deel", doel)
        self._stuur(json.dumps({"ok": True, "naam": naam,
                                "bytes": lengte - over}).encode(),
                    "application/json")

    def do_GET(self):
        if self.path.startswith("/stand.json"):
            try:
                with open(f"{MAP}/stand.json") as f:
                    stand = json.load(f)
            except Exception:
                stand = {}
            with _slot:
                stand["run"] = dict(_run)
            try:
                with open("/home/arch/amber-werk/wachter/stand.json") as f:
                    stand["wachter"] = json.load(f)
            except Exception:
                pass
            # De projecturen, live uit het urenlogboek in de papieren-map.
            # Cley houdt ze daar bij; het venster telt alleen op.
            try:
                with open("/home/arch/amber/uren.md") as f:
                    getallen = re.findall(
                        r"^\|[^|]+\|\s*~?([\d]+(?:[.,]\d+)?)", f.read(), re.M)
                stand["uren"] = round(sum(float(g.replace(",", "."))
                                          for g in getallen), 1)
            except Exception:
                pass
            self._stuur(json.dumps(stand).encode(), "application/json")
        elif self.path.startswith("/stuur"):
            with open(f"{MAP}/stuur.html", "rb") as f:
                self._stuur(f.read())
        elif self.path.startswith("/rapport"):
            naam = os.path.basename(self.path[len("/rapport"):].strip("/")) or "index.html"
            try:
                with open(os.path.join("/home/arch/rapport", naam), "rb") as f:
                    self._stuur(f.read())
            except Exception:
                self._stuur(b"<p>nog geen rapport</p>")
        else:
            with open(f"{MAP}/index.html", "rb") as f:
                self._stuur(f.read())


threading.Thread(target=_ververs_run, daemon=True).start()
ThreadingHTTPServer(("0.0.0.0", 8000), Venster).serve_forever()
