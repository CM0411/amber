"""De wachter — houdt de trainer (nu de Z490) in de gaten, vanaf de DL380.

Bewust vanaf de thuisbasis: als de trainer bevriest is een agent aan boord net zo
dood als de machine. Elke minuut:

  * bereikbaar? zo niet: vastleggen, en blijven proberen
  * opnieuw opgestart? (uptime verspringt) → crash vastleggen, controleren dat
    de trainingsdienst vanzelf terugkwam
  * loopt de training vast? (dienst actief maar het stapnummer beweegt tien
    minuten niet — zoals de code-validatie die stil doodging) → dienst herstarten
  * elke vijf minuten: temperatuur, verbruik en stap vastleggen, zodat een
    volgende crash een spoor heeft (de eerste had er geen)

Alles komt in ~/amber-werk/wachter/ en gaat dus mee in de back-up.
"""
import json, os, re, subprocess, time

# Het wachtwoord van de rekenmachine staat búiten de repo — een repo die ooit
# openbaar wordt mag nooit een geheim in zijn geschiedenis dragen.
def _geheim():
    with open("/home/arch/.amber-geheim") as f:
        return f.read().strip()


MAP = os.path.dirname(os.path.abspath(__file__))
X399 = "arch@192.168.1.239"
LOG = f"{MAP}/x399-logboek.txt"
METINGEN = f"{MAP}/x399-metingen.csv"
STAND = f"{MAP}/stand.json"

toestand = {"bereikbaar": None, "uptime": None, "stap": None,
            "stap_tijd": 0.0, "crashes_vandaag": 0, "dag": time.strftime("%d")}


def ssh(opdracht, tijd=10):
    r = subprocess.run(["sshpass", "-p", _geheim(), "ssh",
                        "-o", f"ConnectTimeout={tijd}",
                        "-o", "StrictHostKeyChecking=no", X399, opdracht],
                       capture_output=True, text=True, timeout=tijd + 15)
    return r.returncode == 0, r.stdout.strip()


def schrijf(regel):
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {regel}\n")
        f.flush(); os.fsync(f.fileno())


def zet_stand(**extra):
    inhoud = {**toestand, "tijd": time.time(), **extra}
    with open(STAND + ".deel", "w") as f:
        json.dump(inhoud, f)
    os.replace(STAND + ".deel", STAND)


schrijf("wachter gestart")
laatste_meting = 0.0
while True:
    try:
        if toestand["dag"] != time.strftime("%d"):
            toestand["dag"] = time.strftime("%d")
            toestand["crashes_vandaag"] = 0

        ok, uit = ssh("uptime -s; systemctl is-active amber-train 2>/dev/null; "
                      "grep -oE 'stap +[0-9]+/' ~/leven.log 2>/dev/null | tail -1")
        nu = time.time()

        if not ok:
            if toestand["bereikbaar"] is not False:
                schrijf("ONBEREIKBAAR — machine plat of netwerk weg")
            toestand["bereikbaar"] = False
            zet_stand(melding="trainer onbereikbaar")
            time.sleep(30)
            continue

        if toestand["bereikbaar"] is False:
            schrijf("weer bereikbaar")
        toestand["bereikbaar"] = True

        regels = uit.splitlines()
        uptime = regels[0] if regels else ""
        dienst = regels[1] if len(regels) > 1 else "?"
        stap_m = re.search(r"stap +(\d+)/", regels[2]) if len(regels) > 2 else None
        stap = int(stap_m.group(1)) if stap_m else None

        if toestand["uptime"] and uptime != toestand["uptime"]:
            toestand["crashes_vandaag"] += 1
            schrijf(f"OPNIEUW OPGESTART (crash {toestand['crashes_vandaag']} "
                    f"vandaag) — nieuwe start: {uptime}; dienst: {dienst}")
        toestand["uptime"] = uptime

        # de dienst komt (weer) op: stilte-teller opnieuw — laden en het
        # startproefwerk duren minuten zonder nieuwe stap (16 aug 2026)
        if dienst == "active" and toestand.get("dienst") != "active":
            toestand["stap_tijd"] = nu
        toestand["dienst"] = dienst

        if stap is not None and stap != toestand["stap"]:
            toestand["stap"] = stap
            toestand["stap_tijd"] = nu

        # dienst hoort te draaien maar het stapnummer beweegt al 10 min niet:
        # stil vastgelopen (30 min: diepe puzzels maken sommige stukken traag,
        # zie 9 aug 2026 — 10 min gaf een herstart-carrousel op stap 2600).
        if (dienst == "active" and toestand["stap"] is not None
                and nu - toestand["stap_tijd"] > 1800):
            schrijf(f"VASTGELOPEN op stap {toestand['stap']} — dienst wordt "
                    f"herstart")
            ssh(f"echo {_geheim()} | sudo -S systemctl restart amber-train 2>/dev/null",
                tijd=20)
            toestand["stap_tijd"] = nu

        # het doel komt uit de runconfiguratie — de vaste 169.999 van run 3
        # liet run 4 (doel 320.000) onbewaakt (gevonden 12 aug 2026)
        try:
            _rc = json.load(open("/home/arch/rapport/run.json"))
            doel, start = _rc["doel"], _rc.get("start")
        except Exception:
            doel, start = 320_000, None
        if dienst == "inactive" and toestand["stap"] is not None \
                and toestand["stap"] < doel - 1:
            # Een run begint alleen op Cleys woord (regel van het project).
            # De wachter mag een gevállen run weer aanzetten — een run die
            # al stappen deed — maar nooit een run die nog moet beginnen: op
            # 16 aug 2026 om 10:57 startte hij run 6 zelf, zeven minuten na
            # de rungrens (run.json zei doel 420.000, de trainer stond stil
            # op 370.000). Sindsdien draagt run.json `start` (het vorige
            # doel); staat de teller daar nog op, of ontbreekt `start`, dan
            # alleen melden — één keer.
            if start is None or toestand["stap"] <= start:
                if not toestand.get("wacht_gemeld"):
                    schrijf("dienst staat uit en de run is nog niet begonnen "
                            f"(stap {toestand['stap']}, start {start}) — ik "
                            "start niets, dat is Cleys woord")
                    toestand["wacht_gemeld"] = True
            else:
                # De vrijgave-pal (18 aug 2026): op de trainer staat een
                # bestand fase1/leven/VRIJGAVE zolang de run mag draaien; een
                # stopwoord haalt het weg. Ontbreekt het, dan is de run
                # bewust gestopt en start de wachter niets — op 18 aug om
                # 18:40 startte hij anders de net gestopte run 7 na zijn
                # eigen boot.
                ok_v, _ = ssh("test -f /home/arch/amber-werk/fase1/leven/VRIJGAVE", tijd=15)
                if not ok_v:
                    if not toestand.get("wacht_gemeld"):
                        schrijf("dienst staat uit en de vrijgave ontbreekt — "
                                "bewust gestopt, ik start niets")
                        toestand["wacht_gemeld"] = True
                else:
                    toestand["wacht_gemeld"] = False
                    schrijf("dienst staat uit terwijl de run al liep en niet af "
                            "is — start hem")
                    ssh(f"echo {_geheim()} | sudo -S systemctl start amber-train "
                        "2>/dev/null", tijd=20)

        # het warmte-oog: elke ronde kijken, geschiedenis elke 5 minuten
        melding = None
        ok2, m = ssh("nvidia-smi --query-gpu=temperature.gpu,power.draw,"
                     "memory.used --format=csv,noheader,nounits")
        if ok2 and m:
            try:
                temp = int(m.split(",")[0].strip())
                if temp >= 80:
                    melding = f"trainer warm: {temp} °C"
                    schrijf(melding)
            except ValueError:
                pass
            if nu - laatste_meting > 300:
                laatste_meting = nu
                nieuw = not os.path.exists(METINGEN)
                with open(METINGEN, "a") as f:
                    if nieuw:
                        f.write("tijd,temp,verbruik,geheugen,stap\n")
                    f.write(f"{time.strftime('%H:%M')},{m.replace(', ', ',')},"
                            f"{toestand['stap']}\n")

        zet_stand(dienst=dienst, melding=melding)
    except Exception as e:
        schrijf(f"wachter-fout: {type(e).__name__}: {e}")
    time.sleep(60)
