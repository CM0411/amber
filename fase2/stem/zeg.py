"""Amber's stem — zeg iets met de op 11 aug 2026 gekozen stem (v22).

  spraak/chatter-venv/bin/python spraak/zeg.py "Hallo Cley." [uit.wav]

De mal en instellingen staan in amber-stem/instellingen.json en wijzigen
alleen als Cley een nieuwe stem kiest.
"""
import json, sys, pathlib

HIER = pathlib.Path(__file__).parent
MET = json.load(open(HIER / "amber-stem" / "instellingen.json"))

import torchaudio
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

tekst = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
doel = sys.argv[2] if len(sys.argv) > 2 else "/home/arch/rapport/zeg.wav"

model = ChatterboxMultilingualTTS.from_local(
    "/home/arch/spraak/chatterbox-model", "cuda")
wav = model.generate(tekst, language_id=MET["language_id"],
                     audio_prompt_path=MET["mal"],
                     exaggeration=MET["exaggeration"],
                     cfg_weight=MET["cfg_weight"],
                     temperature=MET["temperature"])
torchaudio.save(doel, wav, model.sr)
print(doel)
