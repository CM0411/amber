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
             "grep -E '^  stap +[0-9]+ \\|.*ladder' ~/leven.log | tail -1; "
             "echo ===; grep 'wereld open' ~/leven.log | tail -15; "
             "echo ===; grep -E '^  stap +[0-9]+ \\|' ~/leven.log | tail -400; "
             "echo ===; systemctl is-active amber-train; "
             "grep -oE '^=== poging [0-9]+' ~/leven.log | tail -1 "
             "| sed 's/=== //'; "
             "nvidia-smi --query-gpu=temperature.gpu,power.draw,memory.used "
             "--format=csv,noheader 2>/dev/null; "
             "echo ===; tail -60 ~/amber-werk/fase1/leven/logboek.jsonl "
             "2>/dev/null"],
            capture_output=True, text=True)
        if r.returncode == 0:
            ruw = r.stdout.split("===")
            regels = [x for x in ruw[0].strip().splitlines() if x.strip()]
            # het machinedeel: dienst, poging, kaart
            machine = {}
            for m_regel in (ruw[3].splitlines() if len(ruw) > 3 else []):
                m_regel = m_regel.strip()
                if m_regel in ("active", "inactive", "activating", "failed"):
                    machine["dienst"] = m_regel
                elif m_regel.startswith("poging"):
                    machine["poging"] = int(m_regel.split()[1])
                elif "," in m_regel and ("W" in m_regel or "MiB" in m_regel):
                    delen = [d.strip() for d in m_regel.split(",")]
                    machine["temp"] = delen[0]
                    machine["watt"] = delen[1].replace(" W", "")
                    machine["vram"] = delen[2].replace(" MiB", "")
            # de scores van het laatste proefwerk, als losse velden
            proefwerk_scores = {}
            if len(regels) > 1:
                for naam, pct in re.findall(r"(\w+)\s+(\d+)%", regels[1]):
                    proefwerk_scores[naam] = int(pct)
                sm = re.search(r"stap\s+(\d+)", regels[1])
                if sm:
                    proefwerk_scores["_stap"] = int(sm.group(1))
            # écht live: de staart van het logboek heeft per stap een
            # tijdstempel. Het gemiddelde van de laatste tussenpozen is het
            # actuele tempo — mét de proefstappen (die zijn echt werk),
            # zonder de proefwerk-gaten (>60 s, eens per 500 stappen). De
            # mediaan stond hier eerst en flatteerde: die verstopte de
            # proefstappen en gaf 1047 waar het lograatje 1900 zei.
            live = {}
            stap_tijden = []
            for regel_j in (ruw[4].splitlines() if len(ruw) > 4 else []):
                try:
                    rj = json.loads(regel_j)
                except ValueError:
                    continue
                if rj.get("soort") == "stap" and rj.get("stap"):
                    stap_tijden.append((int(rj["stap"]), float(rj["tijd"])))
            if len(stap_tijden) >= 8:
                stap_tijden.sort()
                duren = [b[1] - a[1] for a, b in
                         zip(stap_tijden[-33:], stap_tijden[-32:])
                         if b[0] == a[0] + 1 and 0 < b[1] - a[1] < 60]
                if duren:
                    live = {"stap": stap_tijden[-1][0],
                            "ms": round(sum(duren) / len(duren) * 1000),
                            "tijd": stap_tijden[-1][1]}
            # de runconfiguratie zoals het rapport hem ook leest
            try:
                with open("/home/arch/rapport/run.json") as f:
                    config = json.load(f)
            except Exception:
                config = {}
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
                _run["machine"] = machine
                _run["live"] = live
                _run["scores"] = proefwerk_scores
                _run["config"] = config
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
            # De rapportenlijst voor het uitklapmenu onder de titel.
            try:
                stand["rapporten"] = sorted(
                    f for f in os.listdir("/home/arch/rapport")
                    if f.endswith(".html"))
            except Exception:
                pass
            try:
                with open("/home/arch/amber-werk/wachter/stand.json") as f:
                    stand["wachter"] = json.load(f)
            except Exception:
                pass
            # De projecturen: afgesloten dagen uit het urenlogboek, plus de
            # lopende dag uit de teller — maar alleen als die dag nog níét
            # als regel in uren.md staat, anders telt hij dubbel.
            try:
                with open("/home/arch/amber/uren.md") as f:
                    md = f.read()
                getallen = re.findall(
                    r"^\|[^|]+\|\s*~?([\d]+(?:[.,]\d+)?)", md, re.M)
                uren = sum(float(g.replace(",", ".")) for g in getallen)
                try:
                    with open("/home/arch/amber/uren-live.json") as f:
                        live = json.load(f)
                    j, m, d = live.get("datum", "0-0-0").split("-")
                    maand = ["", "jan", "feb", "mrt", "apr", "mei", "jun",
                             "jul", "aug", "sep", "okt", "nov", "dec"][int(m)]
                    if f"{int(d)} {maand} {j}" not in md:
                        uren += live.get("minuten", 0) / 60
                    stand["haar_uren"] = round(live.get("haar_minuten", 0) / 60, 1)
                except Exception:
                    pass
                stand["uren"] = round(uren, 1)
            except Exception:
                pass
            self._stuur(json.dumps(stand).encode(), "application/json")
        elif self.path.startswith("/stuur"):
            with open(f"{MAP}/stuur.html", "rb") as f:
                self._stuur(f.read())
        elif self.path.startswith("/rapport"):
            naam = os.path.basename(self.path[len("/rapport"):].strip("/")) or "index.html"
            # Het juiste soort per bestand: sinds de spraakproef (11 aug
            # 2026) staan hier ook wav-bestanden, en die spelen alleen af
            # als ze niet als html verstuurd worden.
            soorten = {".wav": "audio/wav", ".png": "image/png",
                       ".svg": "image/svg+xml", ".json": "application/json"}
            soort = soorten.get(os.path.splitext(naam)[1],
                                "text/html; charset=utf-8")
            try:
                with open(os.path.join("/home/arch/rapport", naam), "rb") as f:
                    inhoud = f.read()
            except Exception:
                self._stuur(b"<p>nog geen rapport</p>")
                return
            # Safari vraagt audio in stukjes (Range) en weigert af te
            # spelen als de server dat niet kan — gevonden 11 aug 2026
            # toen de stemproef in de browser stil bleef.
            bereik = self.headers.get("Range")
            if bereik and bereik.startswith("bytes="):
                try:
                    van, tot = (bereik[6:].split("-") + [""])[:2]
                    van = int(van) if van else 0
                    tot = int(tot) if tot else len(inhoud) - 1
                    tot = min(tot, len(inhoud) - 1)
                    stuk = inhoud[van:tot + 1]
                    self.send_response(206)
                    self.send_header("Content-Type", soort)
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Range",
                                     f"bytes {van}-{tot}/{len(inhoud)}")
                    self.send_header("Content-Length", str(len(stuk)))
                    self.end_headers()
                    self.wfile.write(stuk)
                    return
                except (ValueError, IndexError):
                    pass
            self.send_response(200)
            self.send_header("Content-Type", soort)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(inhoud)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(inhoud)
        else:
            with open(f"{MAP}/index.html", "rb") as f:
                self._stuur(f.read())


threading.Thread(target=_ververs_run, daemon=True).start()
ThreadingHTTPServer(("0.0.0.0", 8000), Venster).serve_forever()
