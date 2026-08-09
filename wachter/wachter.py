"""De wachter — houdt de X399 in de gaten, vanaf de DL380.

Bewust vanaf de thuisbasis: als de X399 bevriest is een agent aan boord net zo
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
X399 = "arch@192.168.1.170"
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
            zet_stand(melding="X399 onbereikbaar")
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

        if dienst == "inactive" and toestand["stap"] is not None \
                and toestand["stap"] < 169_999:
            schrijf("dienst staat uit terwijl de run niet af is — start hem")
            ssh(f"echo {_geheim()} | sudo -S systemctl start amber-train 2>/dev/null",
                tijd=20)

        if nu - laatste_meting > 300:
            laatste_meting = nu
            ok2, m = ssh("nvidia-smi --query-gpu=temperature.gpu,power.draw,"
                         "memory.used --format=csv,noheader,nounits")
            if ok2 and m:
                nieuw = not os.path.exists(METINGEN)
                with open(METINGEN, "a") as f:
                    if nieuw:
                        f.write("tijd,temp,verbruik,geheugen,stap\n")
                    f.write(f"{time.strftime('%H:%M')},{m.replace(', ', ',')},"
                            f"{toestand['stap']}\n")

        zet_stand(dienst=dienst, melding=None)
    except Exception as e:
        schrijf(f"wachter-fout: {type(e).__name__}: {e}")
    time.sleep(60)
