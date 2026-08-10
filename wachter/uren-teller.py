"""
De urenteller — weet wanneer er echt gewerkt wordt.

Elke keer dat Cley en Claude aan Amber werken, groeit het gespreksbestand
van de sessie op deze machine. Dit script draait elke vijf minuten
(amber-uren.timer) en kijkt of dat gebeurd is; zo ja, dan tellen die vijf
minuten mee voor vandaag. Geen klok die loopt terwijl niemand er is —
alleen minuten waarin er werkelijk iets gebeurde.

De afgesloten dagen staan in ~/amber/uren.md (bij het dagverslag); dit
bestand draagt alleen de lopende dag. Het venster telt beide op, en slaat
de live-dag over zodra hij als regel in uren.md staat — dan kan er nooit
dubbel geteld worden.
"""

import glob
import json
import os
import time

GESPREKKEN = "/home/arch/.claude/projects/-home-arch-amber/*.jsonl"
STAND = "/home/arch/amber/uren-live.json"
STAP_MINUTEN = 5


def nieuwste_mtime():
    tijden = [os.path.getmtime(p) for p in glob.glob(GESPREKKEN)]
    return max(tijden) if tijden else 0.0


def haar_stap():
    """Waar haar stappenteller staat, volgens de wachter."""
    try:
        with open("/home/arch/amber-werk/wachter/stand.json") as f:
            return int(json.load(f).get("stap") or 0)
    except (FileNotFoundError, ValueError):
        return 0


def hoofd():
    vandaag = time.strftime("%Y-%m-%d")
    try:
        with open(STAND) as f:
            stand = json.load(f)
    except (FileNotFoundError, ValueError):
        stand = {}
    if stand.get("datum") != vandaag:
        # Onze minuten zijn per dag (uren.md draagt de afgesloten dagen);
        # haar leerminuten lopen levenslang door en blijven dus staan.
        stand = {"datum": vandaag, "minuten": 0, "gezien_mtime": 0.0,
                 "haar_minuten": stand.get("haar_minuten", _HAAR_START),
                 "gezien_stap": stand.get("gezien_stap", 0)}
    if "haar_minuten" not in stand:
        stand["haar_minuten"] = _HAAR_START
        stand["gezien_stap"] = 0

    mtime = nieuwste_mtime()
    if mtime > stand.get("gezien_mtime", 0.0):
        stand["minuten"] = int(stand.get("minuten", 0)) + STAP_MINUTEN
    stand["gezien_mtime"] = mtime

    # Haar leertijd: telt alleen als de stappenteller werkelijk vooruitliep.
    stap = haar_stap()
    if stap and stap != stand.get("gezien_stap", 0):
        stand["haar_minuten"] = int(stand["haar_minuten"]) + STAP_MINUTEN
    stand["gezien_stap"] = stap

    with open(STAND + ".deel", "w") as f:
        json.dump(stand, f)
    os.replace(STAND + ".deel", STAND)
    print(f"{vandaag}: wij {stand['minuten']} min, zij {stand['haar_minuten']} min")


# Startwaarde voor haar leertijd, een schatting achteraf (10 aug 2026,
# 23:00): run 1 en de nachtruns ~12 u, metingen ~4 u, run 2 ~5,5 u, run 3
# tot nu ~28 u — samen ~49,5 uur. Vanaf hier telt de teller exact.
_HAAR_START = int(49.5 * 60)


if __name__ == "__main__":
    hoofd()
