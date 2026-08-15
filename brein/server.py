"""Het brein-venster: webserver op de Z490 — de altijd-aan-machine (14 aug 2026).

  /            de levende pagina — cirkel, lagen, wat ze nu doet
  /stand.json  de gegevens erachter (kijker + stand van de grote run)
  /rapport     het laatste nachtrapport

De run leeft op deze machine, dus alles daarover wordt lokaal gelezen.
De GPU-kant (kijker, gesprek, oren, mond, oog) draait op de DL380 en is
er alleen 17:00–23:00; de brug (amber-brug, DL380) sjouwt de bestanden
heen en weer. Valt de DL380 weg, dan blijft de pagina gewoon staan —
alleen de levende hersenweergave en de spraak vallen dan stil.
"""
import json, os, re, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAP = "/home/arch/amber-werk/brein"
DL380 = "arch@192.168.1.51"
SPRAAK_UIT = "/home/arch/spraak-uit"   # verzoeken aan de mond; de brug brengt ze

# de beeldenopvang (Q-voorproef) draait als eigen draad mee
try:
    import beelden
except Exception as _e:
    beelden = None
    print("beelden niet geladen:", _e, flush=True)


def _ssh_dl380(opdracht, tijd=8):
    """Eén bevel naar de thuisbasis, met sleutel en korte tijdslimiet —
    de DL380 is er alleen 's avonds en dit mag het venster nooit ophouden."""
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={tijd}",
         DL380, opdracht], capture_output=True, text=True, timeout=tijd + 12)

_run = {"regel": "", "proefwerk": "", "tijd": 0.0}
_slot = threading.Lock()


def _ververs_run():
    while True:
        # alles over de run staat op deze machine — gewoon lezen dus
        r = subprocess.run(
            ["bash", "-c",
             "grep -E 'ms/st' ~/leven.log | tail -1; "
             "grep -E '^  stap +[0-9]+ \\|.*ladder' ~/leven.log | tail -1; "
             "echo ===; grep 'wereld open' ~/leven.log | tail -15; "
             "echo ===; grep -E '^  stap +[0-9]+ \\|' ~/leven.log | tail -400; "
             "echo ===; systemctl is-active amber-train; "
             "grep -oE '^=== poging [0-9]+' ~/leven.log | tail -1 "
             "| sed 's/=== //'; "
             "nvidia-smi --query-gpu=temperature.gpu,power.draw,memory.used "
             "--format=csv,noheader 2>/dev/null; "
             "sensors 2>/dev/null | grep -m1 'Package id 0' "
             "| grep -oE '[0-9]+[.][0-9]' | head -1; "
             "grep -o 'resync = [0-9.]*%' /proc/mdstat 2>/dev/null "
             "|| echo spiegel-synchroon; "
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
                elif m_regel.replace(".", "").isdigit():
                    machine["cpu_temp"] = m_regel
                elif "spiegel" in m_regel or "resync" in m_regel:
                    machine["spiegel"] = m_regel.replace("resync = ",
                                                         "synchroniseert ")
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
            # het thuis-blok: de DL380, alleen 's avonds aan — één
            # ssh-bevel, en blijft hij stil dan zegt de pagina dat eerlijk
            thuis = {}
            try:
                r2 = _ssh_dl380(
                    "nvidia-smi --query-gpu=temperature.gpu,power.draw "
                    "--format=csv,noheader 2>/dev/null; echo ===; "
                    "sensors 2>/dev/null | grep -m1 '^temp1:'; echo ===; "
                    "cat /proc/mdstat 2>/dev/null; echo ===; "
                    "systemctl is-active amber-kijker amber-brug "
                    "amber-gesprek amber-oren amber-mond amber-oog; true")
                if r2.returncode == 0:
                    t = r2.stdout.split("===")
                    thuis["aan"] = True
                    thuis["kaarten"] = [x.strip() for x in
                                        t[0].strip().splitlines()]
                    for sr in (t[1] if len(t) > 1 else "").splitlines():
                        sr = sr.strip()
                        if sr.startswith("temp1:"):
                            thuis["cpu_temp"] = sr.split("+")[1].split("°")[0]
                            break
                    md = t[2] if len(t) > 2 else ""
                    thuis["array"] = ("synchroniseert" if "resync" in md
                                      else "synchroon" if "md127" in md
                                      else "geen array")
                    namen = ["kijker", "brug", "gesprek", "oren", "mond",
                             "oog"]
                    thuis["diensten"] = dict(zip(
                        namen, (t[3] if len(t) > 3 else "").strip()
                        .splitlines()))
                else:
                    thuis["aan"] = False
            except Exception:
                thuis["aan"] = False
            with _slot:
                _run["thuis"] = thuis
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
        elif self.path.startswith("/spreek"):
            # bouw een gesproken stand en leg hem in de wachtrij van de mond
            with _slot:
                r = dict(_run)
            lv = r.get("live") or {}
            cfg = r.get("config") or {}
            sc = r.get("scores") or {}
            delen = []
            if lv.get("stap") and cfg.get("doel"):
                pct = 100 * lv["stap"] // cfg["doel"]
                delen.append("Ik ben bij stap "
                             + f"{lv['stap']:,}".replace(",", " ")
                             + f", dat is {pct} procent van deze run")
            if lv.get("ms"):
                delen.append(f"Een stap kost mij nu {lv['ms']} milliseconden")
            db = r.get("doorbraken") or []
            if db:
                delen.append(f"Mijn laatste doorbraak was {db[-1]['familie']} "
                             f"tot diepte {db[-1]['tot']}")
            if sc.get("grondslag") is not None:
                delen.append(f"Op het grondslagproefwerk sta ik op "
                             f"{sc['grondslag']} procent")
            tekst = (". ".join(delen) + "."
                     if delen else "Ik heb nog niets te vertellen.")
            # niet rechtstreeks in de zeg-wachtrij: de mond woont op de
            # DL380. Hier klaarleggen, de brug brengt het (.deel eerst —
            # de brug mag nooit een half verzoek meenemen)
            os.makedirs(SPRAAK_UIT, exist_ok=True)
            pad = f"{SPRAAK_UIT}/stem-stand.txt"
            with open(pad + ".deel", "w") as f:
                f.write(tekst)
            os.replace(pad + ".deel", pad)
            self._stuur(json.dumps({"aangevraagd": True}).encode(),
                        "application/json")
        elif self.path.startswith("/vraag-stel"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query).get("q", [""])[0]
            q = q.strip()[:200]
            # een x tussen cijfers bedoelt vermenigvuldigen — zij kent de
            # letter x alleen uit lijstfilters en antwoordt anders in díé
            # taal (Cleys ontdekking, 12 aug 2026)
            q = re.sub(r"(?<=[\d\s])[xX](?=[\d\s])", "*", q)
            if q:
                os.makedirs(f"{MAP}/vraag-wachtrij", exist_ok=True)
                with open(f"{MAP}/vraag-wachtrij/{time.time():.2f}.txt",
                          "w") as f:
                    f.write(q)
            self._stuur(json.dumps({"gesteld": bool(q)}).encode(),
                        "application/json")
        elif self.path.startswith("/les-leer"):
            # "Leer haar dit": vraag + het juiste antwoord de brievenbus in.
            # De les gaat pas op een rungrens naar haar logboek (één
            # schrijver) en dan bij de volgende start het geheugen in —
            # nooit haar eigen antwoord, de correctie is de les.
            from urllib.parse import urlparse, parse_qs
            velden = parse_qs(urlparse(self.path).query)
            vraag = velden.get("vraag", [""])[0].strip()[:400]
            antwoord = velden.get("antwoord", [""])[0].strip()[:400]
            # zelfde x-herschrijving als bij het stellen: de les moet er
            # uitzien zoals zij de vraag te zien krijgt
            vraag = re.sub(r"(?<=[\d\s])[xX](?=[\d\s])", "*", vraag)
            if vraag and antwoord:
                # onder het gedeelde slot: de bezorging (rungrens) wisselt
                # dit bestand om, en de brug hangt er ook aan — zonder slot
                # kan een les precies in die wissel stil verdwijnen
                import fcntl
                bus = "/home/arch/amber-werk/fase1/brievenbus.jsonl"
                with open(bus + ".slot", "w") as s:
                    fcntl.flock(s, fcntl.LOCK_EX)
                    with open(bus, "a") as f:
                        f.write(json.dumps({
                            "tijd": time.time(),
                            "wanneer": time.strftime("%Y-%m-%d %H:%M"),
                            "soort": "les", "bron": "vraag-tab",
                            "vraag": vraag, "antwoord": antwoord,
                            "bezorgd": False,
                        }, ensure_ascii=False) + "\n")
                        f.flush()
                        os.fsync(f.fileno())
            self._stuur(json.dumps(
                {"in_brievenbus": bool(vraag and antwoord)}).encode(),
                "application/json")
        elif self.path.startswith("/gesprek.json"):
            try:
                with open(f"{MAP}/gesprek.json", "rb") as f:
                    self._stuur(f.read(), "application/json")
            except Exception:
                self._stuur(b'{"beurten": [], "status": "rust"}',
                            "application/json")
        elif self.path.startswith("/gesprek-zeg"):
            # een getypte gespreksbeurt: in de gesprek-inbox, de regisseur
            # (gesprek.py) pakt hem op. Eerst .deel, dan hernoemen — de
            # regisseur mag nooit een half bericht lezen
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query).get("q", [""])[0]
            q = q.strip()[:200]
            if q:
                os.makedirs(f"{MAP}/gesprek-inbox", exist_ok=True)
                pad = f"{MAP}/gesprek-inbox/{time.time():.2f}.txt"
                with open(pad + ".deel", "w") as f:
                    f.write(q)
                os.replace(pad + ".deel", pad)
            self._stuur(json.dumps({"gezegd": bool(q)}).encode(),
                        "application/json")
        elif self.path.startswith("/gesprek"):
            with open(f"{MAP}/gesprek.html", "rb") as f:
                self._stuur(f.read())
        elif self.path.startswith("/vraag-antwoord.json"):
            try:
                with open(f"{MAP}/vraag-antwoord.json", "rb") as f:
                    self._stuur(f.read(), "application/json")
            except Exception:
                self._stuur(b"{}", "application/json")
        elif self.path.startswith("/vraag"):
            with open(f"{MAP}/vraag.html", "rb") as f:
                self._stuur(f.read())
        elif self.path.startswith("/zoek"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query).get("q", [""])[0]
            q = q.strip()[:120]
            # zij schrijft * — wie x typt bedoelt hetzelfde
            q = re.sub(r"(?<=[\d\s])[xX](?=[\d\s])", "*", q)
            uit = []
            if len(q) >= 2:
                def grams(t):
                    t = t.replace(" ", "")
                    return {t[i:i + 3] for i in range(len(t) - 2)}
                doel = grams(q)
                plat = q.replace(" ", "")
                try:
                    with open(f"{MAP}/herinneringen.json") as f:
                        alles = json.load(f)
                except Exception:
                    alles = []
                scores = []
                for m in alles:
                    kaal = m["opgave"].replace(" ", "")
                    # letterlijk raak telt het zwaarst — korte
                    # zoekopdrachten hebben te weinig 3-grammen om op
                    # gelijkenis te varen
                    if plat and plat in kaal:
                        scores.append((1.0, m))
                        continue
                    overlap = len(doel & grams(m["opgave"]))
                    if overlap:
                        scores.append(
                            (overlap / len(doel | grams(m["opgave"])), m))
                scores.sort(key=lambda x: -x[0])
                uit = [{**m, "gelijkenis": round(sc, 2)}
                       for sc, m in scores[:12]]
            self._stuur(json.dumps({"gevonden": uit,
                                    "totaal": len(alles) if q else 0},
                                   ensure_ascii=False).encode(),
                        "application/json")
        elif self.path.startswith("/geheugen"):
            with open(f"{MAP}/geheugen.html", "rb") as f:
                self._stuur(f.read())
        elif self.path.startswith("/dagbericht-nu"):
            # het dagbericht wordt op de DL380 gemaakt (de mond woont daar)
            r = _ssh_dl380("python3 /home/arch/spraak/dagbericht.py", 20)
            self._stuur(json.dumps(
                {"aangevraagd": r.returncode == 0}).encode(),
                "application/json")
        elif self.path.startswith("/dagbericht"):
            with open(f"{MAP}/dagbericht.html", "rb") as f:
                self._stuur(f.read())
        elif self.path.startswith("/machines"):
            with open(f"{MAP}/machines.html", "rb") as f:
                self._stuur(f.read())
        elif self.path.startswith("/gebeurtenissen"):
            with open(f"{MAP}/gebeurtenissen.html", "rb") as f:
                self._stuur(f.read())
        elif self.path.startswith("/opname"):
            with open(f"{MAP}/opname.html", "rb") as f:
                self._stuur(f.read())
        elif self.path.startswith("/onderweg"):
            with open(f"{MAP}/onderweg.html", "rb") as f:
                self._stuur(f.read())
        elif self.path.startswith("/beelden.json"):
            try:
                with open("/home/arch/amber-werk/fase2/beelden/stand.json",
                          "rb") as f:
                    self._stuur(f.read(), "application/json")
            except Exception:
                self._stuur(b'{"totaal": 0, "per_rit": {}}',
                            "application/json")
        elif self.path.startswith("/stuur"):
            with open(f"{MAP}/stuur.html", "rb") as f:
                self._stuur(f.read())
        elif self.path.startswith("/rapport"):
            # de verversingscode (?tijd) hoort niet bij de bestandsnaam —
            # zonder dit strippen zocht de server naar "dagbericht.wav?123"
            # en speelde er stilte (gevonden 12 aug 2026, Cleys oren)
            schoon = self.path.split("?")[0]
            naam = os.path.basename(schoon[len("/rapport"):].strip("/")) or "index.html"
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


class Mobiel(Venster):
    """Poort 8001: dezelfde gegevens, maar de wortel is de telefoonpagina —
    gebouwd voor de duim in plaats van geperst vanaf het grote scherm."""
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            with open(f"{MAP}/mobiel.html", "rb") as f:
                self._stuur(f.read())
        else:
            super().do_GET()


threading.Thread(target=_ververs_run, daemon=True).start()
# de gesprekslus draait níét hier: oren, mond en kijker wonen op de
# DL380, dus daar draait gesprek.py als eigen dienst (amber-gesprek)
if beelden:
    threading.Thread(target=beelden.lus, daemon=True).start()
threading.Thread(target=lambda: ThreadingHTTPServer(
    ("0.0.0.0", 8001), Mobiel).serve_forever(), daemon=True).start()
ThreadingHTTPServer(("0.0.0.0", 8000), Venster).serve_forever()
