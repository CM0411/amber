"""De luisteraar — haar oren (O, fase 2), eerste versie.

Kijkt elke paar seconden in de inbox. Elk nieuw geluidsbestand (van de
opnamepagina of de stuur-pagina) gaat door whisper (Nederlands, lokaal op
de P100) en het verstane komt in rapport/gehoord.json, dat de
opnamepagina laat zien. Geleend model, zoals de roadmap voorschrijft:
wat waarneemt lenen we, wat leert bouwen we zelf.
"""
import json
import os
import time

INBOX = "/home/arch/inbox"
UIT = "/home/arch/rapport/gehoord.json"
VERWERKT = "/home/arch/spraak/gehoord-verwerkt.json"
# De brievenbus: alles wat ze verstaat wordt hier duurzaam bewaard als
# waarneming-in-wording, en bij een rungrens in haar logboek bezorgd
# (bezorg-brievenbus.py). Buiten git (privé), binnen de back-ups.
BRIEVENBUS = "/home/arch/amber-werk/fase1/brievenbus.jsonl"
SOORTEN = (".m4a", ".mp3", ".wav", ".webm", ".ogg", ".aac", ".flac")

import whisper
model = whisper.load_model("medium", device="cuda")
print("oren wakker: whisper medium op de kaart", flush=True)

try:
    verwerkt = set(json.load(open(VERWERKT)))
except Exception:
    verwerkt = set()

def schrijf_gehoord(regels):
    tmp = UIT + ".deel"
    with open(tmp, "w") as f:
        json.dump({"gehoord": regels[-20:]}, f, ensure_ascii=False)
    os.replace(tmp, UIT)

try:
    regels = json.load(open(UIT))["gehoord"]
except Exception:
    regels = []

while True:
    try:
        for naam in sorted(os.listdir(INBOX)):
            if not naam.lower().endswith(SOORTEN) or naam in verwerkt:
                continue
            pad = os.path.join(INBOX, naam)
            # half geüpload? dan is hij binnen 2 s nog gegroeid
            m1 = os.path.getsize(pad); time.sleep(2)
            if os.path.getsize(pad) != m1:
                continue
            print("luistert naar:", naam, flush=True)
            uit = model.transcribe(pad, language="nl", fp16=False)
            tekst = (uit.get("text") or "").strip() or "(niets verstaan)"
            regels.append({"bestand": naam[:48],
                           "tijd": time.strftime("%H:%M"),
                           "tekst": tekst})
            schrijf_gehoord(regels)
            with open(BRIEVENBUS, "a") as f:
                f.write(json.dumps({
                    "tijd": time.time(),
                    "wanneer": time.strftime("%Y-%m-%d %H:%M"),
                    "bron": "spraak", "bestand": naam[:64],
                    "tekst": tekst, "bezorgd": False,
                }, ensure_ascii=False) + "\n")
            verwerkt.add(naam)
            with open(VERWERKT + ".deel", "w") as f:
                json.dump(sorted(verwerkt), f)
            os.replace(VERWERKT + ".deel", VERWERKT)
            print("verstaan:", tekst[:80], flush=True)
    except Exception as e:
        print("oren-hapering:", e, flush=True)
        time.sleep(10)
    time.sleep(3)
