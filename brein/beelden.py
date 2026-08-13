"""Beelden onderweg — de opvang vóór er een oog is (Q-voorbereiding, 13 aug).

Q brengt losse beelden mee van ritten ("beeld als losse beelden, niet als
stroom" — register 6 aug). Er is nog geen oog: welk geleend beeldmodel
naar de foto's gaat kijken is een open ontwerpkeuze voor Cley. Maar wat
onderweg wordt vastgelegd mag ondertussen niet verdampen of de inbox
verstoppen. Deze lus haalt fotobestanden uit de inbox en legt ze
geordend per rit klaar in fase2/beelden/, met een telling die de
onderweg-pagina laat zien.

De luisteraar (audio) en deze lus (beeld) delen de inbox en pakken elk
alleen hun eigen soorten; de upload-route schrijft atomair (.deel en dan
hernoemen), dus een half bestand bestaat hier niet.

Net als gesprek.py: daemon-thread in server.py, alleen standaardbibliotheek.
"""
import json
import os
import re
import time

INBOX = "/home/arch/inbox"
DOEL = "/home/arch/amber-werk/fase2/beelden"
SOORTEN = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif")
RIT = re.compile(r"^rit-(\d+)-")


def _stand():
    per_rit = {}
    totaal = 0
    try:
        for rit in sorted(os.listdir(DOEL)):
            pad = os.path.join(DOEL, rit)
            if os.path.isdir(pad):
                n = len(os.listdir(pad))
                per_rit[rit] = n
                totaal += n
    except OSError:
        pass
    uit = {"totaal": totaal, "per_rit": per_rit, "tijd": time.time()}
    with open(os.path.join(DOEL, "stand.json.deel"), "w") as f:
        json.dump(uit, f)
    os.replace(os.path.join(DOEL, "stand.json.deel"),
               os.path.join(DOEL, "stand.json"))


def lus():
    os.makedirs(DOEL, exist_ok=True)
    _stand()
    print("beeldenopvang wakker", flush=True)
    while True:
        try:
            beweging = False
            for naam in sorted(os.listdir(INBOX)):
                if not naam.lower().endswith(SOORTEN):
                    continue
                m = RIT.match(naam)
                rit = f"rit-{m.group(1)}" if m else "los"
                map_ = os.path.join(DOEL, rit)
                os.makedirs(map_, exist_ok=True)
                os.replace(os.path.join(INBOX, naam),
                           os.path.join(map_, naam))
                print("beeld bewaard:", rit + "/" + naam[:60], flush=True)
                beweging = True
            if beweging:
                _stand()
        except Exception as e:
            print("beelden-hapering:", e, flush=True)
            time.sleep(10)
        time.sleep(3)


if __name__ == "__main__":
    lus()
