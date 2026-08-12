"""De melder — belangrijke gebeurtenissen als pushbericht op Cleys telefoon.

Kijkt elke halve minuut naar de levende stand en meldt alleen verándering:
een doorbraak, de trainer te warm of onbereikbaar, de dienst gevallen
terwijl de run niet af is, en de finish zelf. Via ntfy.sh met een geheim
kanaal (staat in ~/.amber-ntfy, buiten de repo); de berichten zelf zijn
karig — een doorbraakregel, geen inhoud van haar geheugen of gesprekken.
"""
import json
import time
import urllib.request

KANAAL = open("/home/arch/.amber-ntfy").read().strip()
STAND = "/home/arch/amber-werk/wachter/melder-stand.json"


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


def haal_stand():
    with urllib.request.urlopen("http://127.0.0.1:8000/stand.json",
                                timeout=10) as r:
        return json.load(r)


try:
    onthouden = json.load(open(STAND))
except Exception:
    onthouden = {"doorbraak": 0, "melding": None, "dienst": "active",
                 "klaar_gemeld": False}

while True:
    try:
        s = haal_stand()
        run = s.get("run") or {}
        lv = run.get("live") or {}
        cfg = run.get("config") or {}
        w = s.get("wachter") or {}
        rm = run.get("machine") or {}

        db = run.get("doorbraken") or []
        if db and db[-1]["stap"] > onthouden["doorbraak"]:
            d = db[-1]
            stuur("Doorbraak",
                  f"{d['familie']} open tot diepte {d['tot']} "
                  f"(stap {d['stap']:,})".replace(",", "."))
            onthouden["doorbraak"] = d["stap"]

        melding = w.get("melding")
        if melding and melding != onthouden["melding"]:
            stuur("Let op", melding, "high")
        onthouden["melding"] = melding

        dienst = rm.get("dienst") or "?"
        doel = cfg.get("doel") or 0
        stap = lv.get("stap") or 0
        if (dienst != "active" and onthouden["dienst"] == "active"
                and stap and doel and stap < doel - 1):
            stuur("Trainer gevallen",
                  f"dienst {dienst} bij stap {stap:,}".replace(",", ".")
                  + " — de wachter probeert een herstart", "high")
        onthouden["dienst"] = dienst

        if doel and stap >= doel and not onthouden["klaar_gemeld"]:
            stuur("Run klaar 🎉",
                  f"{cfg.get('naam', 'de run')} heeft zijn doel van "
                  f"{doel:,} stappen gehaald".replace(",", "."), "high")
            onthouden["klaar_gemeld"] = True
        if doel and stap < doel:
            onthouden["klaar_gemeld"] = False

        with open(STAND + ".deel", "w") as f:
            json.dump(onthouden, f)
        import os
        os.replace(STAND + ".deel", STAND)
    except Exception as e:
        print("melder-hapering:", e, flush=True)
    time.sleep(30)
