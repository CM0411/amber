"""De mond — haar stem, warm geladen (O, fase 2).

Chatterbox met de op 11 aug gekozen v22-stem blijft in het geheugen van
kaart 1 staan. Alles wat in de wachtrij-map verschijnt (een tekstbestand)
wordt uitgesproken naar rapport/stem-stand.wav, met een json ernaast
zodat het venster weet wanneer er iets nieuws te horen is.
"""
import json
import os
import time

WACHTRIJ = "/home/arch/spraak/zeg-wachtrij"
RAPPORT = "/home/arch/rapport"
MET = json.load(open("/home/arch/spraak/amber-stem/instellingen.json"))

os.makedirs(WACHTRIJ, exist_ok=True)

import re
import sys
sys.path.insert(0, "/home/arch/spraak")
from getallen import vertaal_tekst

import torch
import torchaudio
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
model = ChatterboxMultilingualTTS.from_local(
    "/home/arch/spraak/chatterbox-model", "cuda:1")
print("mond wakker: v22 op kaart 1", flush=True)

while True:
    try:
        for naam in sorted(os.listdir(WACHTRIJ)):
            pad = os.path.join(WACHTRIJ, naam)
            tekst = open(pad).read().strip()
            os.remove(pad)
            if not tekst:
                continue
            # de bestandsnaam van de wachtrij is de bestemming:
            # stem-stand.txt -> rapport/stem-stand.wav (+ .json), enz.
            doel = os.path.splitext(os.path.basename(naam))[0] or "stem-stand"
            wav_uit = os.path.join(RAPPORT, doel + ".wav")
            meld_uit = os.path.join(RAPPORT, doel + ".json")
            # getallen worden woorden (cijfers breken de uitspraak) en
            # het spreken gaat zin voor zin — één lange lap laat het
            # model zwalken en herhalen (gehoord op 12 aug 2026)
            tekst = vertaal_tekst(tekst)
            zinnen = [z.strip() for z in
                      re.split(r"(?<=[.!?])\s+", tekst) if z.strip()]
            print("spreekt naar", doel, ":", len(zinnen), "zinnen", flush=True)
            stukken = []
            stilte = None
            for zin in zinnen:
                w = model.generate(zin, language_id=MET["language_id"],
                                   audio_prompt_path=MET["mal"],
                                   exaggeration=MET["exaggeration"],
                                   cfg_weight=MET["cfg_weight"],
                                   temperature=MET["temperature"])
                if stilte is None:
                    stilte = torch.zeros(w.shape[0], int(model.sr * 0.24))
                stukken += [w, stilte]
            wav = torch.cat(stukken[:-1], dim=1)
            # tijdelijk bestand mét .wav-erin: torchaudio kijkt hardnekkig
            # naar de bestandsnaam, wat we ook meegeven (12 aug 2026)
            torchaudio.save(wav_uit + ".deel.wav", wav, model.sr)
            os.replace(wav_uit + ".deel.wav", wav_uit)
            with open(meld_uit + ".deel", "w") as f:
                json.dump({"tijd": time.time(), "tekst": tekst}, f,
                          ensure_ascii=False)
            os.replace(meld_uit + ".deel", meld_uit)
    except Exception as e:
        print("mond-hapering:", e, flush=True)
        time.sleep(5)
    time.sleep(1.5)
