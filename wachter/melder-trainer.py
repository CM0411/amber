"""De melder aan boord van de trainer (Z490) — piept ook als de DL380 uit is.

Leest de stand rechtstreeks van de machine zelf: de laatste logregel
(`stap 273400/320000`), de dienststatus en de kaarttemperatuur. Geen
venster ertussen, want dat draait op de DL380 en die is overdag uit.
Via ntfy.sh met het geheime kanaal (staat in ~/.amber-ntfy, buiten de
repo); de berichten zijn karig — een stand, geen inhoud.

Wat hij meldt: de finish, de dienst gevallen terwijl de run niet af is,
tien minuten stilstand (dan herstart hij de dienst ook zelf, hoogstens
één keer per kwartier), een kaart van 80 graden of heter, en sinds 16 aug
2026 de wereld die op slot zit: SLOT_NA stappen zonder dat er ergens een
diepte openging (één melding per slot; Cley beslist over een rungrens),
en apart de wereld die dicht is — elke familie tegen zijn hek.
"""
import json
import os
import re
import subprocess
import time
import urllib.request

KANAAL = open("/home/arch/.amber-ntfy").read().strip()
LOG = "/home/arch/leven.log"
STAND = "/home/arch/amber-werk/wachter/melder-trainer-stand.json"

STILSTAND_NA = 600      # seconden zonder nieuwe stap voordat hij ingrijpt
HERSTART_RUST = 900     # minimale rust tussen twee eigen herstarts
WARM_VANAF = 80         # graden; melding gaat pas opnieuw onder de 75
SLOT_NA = 5000          # stappen zonder nieuwe opening → "wereld op slot", één melding
RUNJSON = "/home/arch/rapport/run.json"


def stuur(titel, tekst, prioriteit="default"):
    try:
        verzoek = urllib.request.Request(
            f"https://ntfy.sh/{KANAAL}", data=tekst.encode(),
            headers={"Title": titel.encode("ascii", "ignore").decode(),
                     "Priority": prioriteit, "Tags": "brain"})
        urllib.request.urlopen(verzoek, timeout=15)
        print("gemeld:", titel, "—", tekst[:60], flush=True)
    except Exception as e:
        print("melden mislukte:", e, flush=True)


def lees_stap():
    """Laatste `stap N/doel` uit het logboek, of (None, None)."""
    try:
        with open(LOG, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 4096))
            staart = f.read().decode(errors="ignore")
        treffers = re.findall(r"stap (\d+)/(\d+)", staart)
        if treffers:
            stap, doel = treffers[-1]
            return int(stap), int(doel)
    except Exception as e:
        print("log lezen mislukte:", e, flush=True)
    return None, None


def lees_proefwerk():
    """Laatste proefwerkregel uit het logboek: {naam: pct}, of {}.

    De namen komen uit de regel zelf, niet uit een vaste lijst — dezelfde
    les als bij het rapport (14 aug 2026): een nieuw proefwerk doet
    vanzelf mee."""
    try:
        with open(LOG, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 16384))
            staart = f.read().decode(errors="ignore")
        regels = re.findall(r"stap\s+\d+ \|((?:\s+\w+\s+\d+%)+)", staart)
        if regels:
            return {n: int(v) for n, v in
                    re.findall(r"(\w+)\s+(\d+)%", regels[-1])}
    except Exception as e:
        print("proefwerk lezen mislukte:", e, flush=True)
    return {}


def lees_wereld():
    """Alle `stap N | wereld open: familie tot D` uit de logstaart:
    {familie: (diepte, stap)} met per familie de laatste. Het logboek wordt
    bij een herstart afgekapt, dus de melder onthoudt zelf wat hij ooit
    zag (zie hieronder) en dit is alleen wat er nú te lezen valt."""
    gezien = {}
    try:
        with open(LOG, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 262144))
            staart = f.read().decode(errors="ignore")
        for stap, rest in re.findall(r"stap\s+(\d+) \| wereld open: ([^\n]+)", staart):
            for fam, diepte in re.findall(r"(\w+) tot (\d+)", rest):
                gezien[fam] = (int(diepte), int(stap))
    except Exception as e:
        print("wereld lezen mislukte:", e, flush=True)
    return gezien


def lees_run():
    """run.json: naam, doel, start en de hekken {familie: diepte}."""
    try:
        rc = json.load(open(RUNJSON))
        hek = {f: int(d) for f, d in re.findall(r"(\w+) (\d+)", rc.get("hek", ""))}
        return rc.get("naam"), rc.get("start"), hek
    except Exception:
        return None, None, {}


def dienst_status():
    uit = subprocess.run(["systemctl", "is-active", "amber-train"],
                         capture_output=True, text=True)
    return uit.stdout.strip() or "?"


def kaart_temp():
    try:
        uit = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu",
             "--format=csv,noheader"], capture_output=True, text=True)
        return int(uit.stdout.strip().splitlines()[0])
    except Exception:
        return None


try:
    onthouden = json.load(open(STAND))
except Exception:
    onthouden = {"stap": 0, "stap_sinds": time.time(), "dienst": "active",
                 "klaar_gemeld": False, "warm_gemeld": False,
                 "herstart_om": 0}

while True:
    try:
        stap, doel = lees_stap()
        dienst = dienst_status()
        temp = kaart_temp()
        nu = time.time()

        # Wordt de dienst (weer) actief, dan begint de stilte-teller opnieuw:
        # de eerste minuten van een run zijn laden en het startproefwerk,
        # zonder nieuwe stap. Geteld vanaf de laatste stap in het log — uren
        # oud na een rungrens — herstartte de melder run 6 op 16 aug 2026 om
        # 11:01 na vier minuten voor niets.
        if dienst == "active" and onthouden.get("dienst") != "active":
            onthouden["stap_sinds"] = nu

        if stap is not None:
            if stap != onthouden["stap"]:
                onthouden["stap"] = stap
                onthouden["stap_sinds"] = nu

            if doel and stap >= doel and not onthouden["klaar_gemeld"]:
                stuur("Run klaar 🎉",
                      f"doel van {doel:,} stappen gehaald".replace(",", "."),
                      "high")
                onthouden["klaar_gemeld"] = True
            if doel and stap < doel:
                onthouden["klaar_gemeld"] = False

            loopt_nog = doel and stap < doel - 1

            if (dienst != "active" and onthouden["dienst"] == "active"
                    and loopt_nog):
                stuur("Trainer gevallen",
                      f"dienst {dienst} bij stap {stap:,}".replace(",", ".")
                      + " — systemd probeert een herstart", "high")

            stil = nu - onthouden["stap_sinds"]
            if (dienst == "active" and loopt_nog and stil > STILSTAND_NA
                    and nu - onthouden["herstart_om"] > HERSTART_RUST):
                stuur("Trainer staat stil",
                      f"{int(stil / 60)} min geen stap (bij "
                      f"{stap:,}".replace(",", ".") + ") — ik herstart de "
                      "dienst", "high")
                subprocess.run(["sudo", "-n", "systemctl", "restart",
                                "amber-train"])
                onthouden["herstart_om"] = nu
                onthouden["stap_sinds"] = nu

        onthouden["dienst"] = dienst

        # proefwerk-sprongen: een cijfer dat ≥ 10 punten verschuift sinds
        # de laatst gemelde stand is een melding waard (Cley, 14 aug 2026:
        # de meldingen dat er iets bereikt is zijn juist fijn). De eerste
        # waarneming van een proefwerk wordt stil onthouden, anders regent
        # het meldingen bij de eerste meting van een run.
        pw = lees_proefwerk()
        gemeld = onthouden.setdefault("proefwerk", {})
        sprongen = []
        for naam, pct in pw.items():
            if naam not in gemeld:
                gemeld[naam] = pct
            elif abs(pct - gemeld[naam]) >= 10:
                pijl = "📈" if pct > gemeld[naam] else "📉"
                sprongen.append(f"{pijl} {naam}: {gemeld[naam]}% → {pct}%")
                gemeld[naam] = pct
        if sprongen:
            stuur("Proefwerk-sprong", " · ".join(sprongen))

        # De wereld op slot (16 aug 2026, Cleys wens): gaat er SLOT_NA
        # stappen lang nergens een diepte open, dan één melding — Cley
        # beslist dan over een rungrens; de melder start of stopt niets.
        # Los daarvan: is elke familie tegen zijn hek, dan is de wereld
        # dicht en is dat het bericht (ook één keer). De baseline is de
        # start van de run (run.json), zodat een verse run niet meteen
        # "op slot" heet; de laatst geziene openingen reizen mee in de
        # eigen stand, want het logboek wordt bij een herstart afgekapt.
        naam, start, hek = lees_run()
        wereld = onthouden.setdefault("wereld", {})
        if naam != onthouden.get("wereld_run"):
            wereld.clear()                        # een nieuwe run: schone lei
            onthouden["wereld_run"] = naam
            onthouden["slot_gemeld_bij"] = None
            onthouden["dicht_gemeld"] = False
        for fam, (diepte, bij) in lees_wereld().items():
            if fam not in wereld or diepte > wereld[fam][0]:
                wereld[fam] = [diepte, bij]
        if stap is not None and dienst == "active" and doel and stap < doel:
            laatst_open = max([bij for _, bij in wereld.values()] + [int(start or 0)])
            if wereld and hek and all(wereld.get(f, [0])[0] >= d for f, d in hek.items()):
                if not onthouden.get("dicht_gemeld"):
                    stuur("Wereld dicht",
                          "elke familie staat tegen zijn hek ("
                          + ", ".join(f"{f} {wereld[f][0]}" for f in hek)
                          + f") bij stap {stap:,}".replace(",", ".")
                          + " — rungrens overwegen? Jij beslist.")
                    onthouden["dicht_gemeld"] = True
            elif (stap - laatst_open >= SLOT_NA
                    and onthouden.get("slot_gemeld_bij") != laatst_open):
                stuur("Wereld op slot",
                      f"al {stap - laatst_open:,} stappen ging nergens een diepte "
                      f"open (laatst bij stap {laatst_open:,}; nu {stap:,}, wereld "
                      .replace(",", ".")
                      + ", ".join(f"{f} {d}" for f, (d, _) in sorted(wereld.items()))
                      + ") — rungrens overwegen? Jij beslist.")
                onthouden["slot_gemeld_bij"] = laatst_open

        if temp is not None:
            if temp >= WARM_VANAF and not onthouden["warm_gemeld"]:
                stuur("Trainer te warm", f"kaart op {temp} °C", "high")
                onthouden["warm_gemeld"] = True
            if temp < WARM_VANAF - 5:
                onthouden["warm_gemeld"] = False

        with open(STAND + ".deel", "w") as f:
            json.dump(onthouden, f)
        os.replace(STAND + ".deel", STAND)
    except Exception as e:
        print("melder-hapering:", e, flush=True)
    time.sleep(30)
