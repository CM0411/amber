"""Het oog — Qwen2.5-VL 3B kijkt naar de foto's van onderweg (Q/O, 13 aug 2026).

Geleend model, zoals de roadmap voorschrijft: wat waarneemt lenen we,
wat leert bouwen we zelf. Gekozen door Cley op 13 aug 2026 (eerste van
drie kandidaten, meteen raak): draait op kaart 1 naast de mond, spreekt
zelf Nederlands, en leest zelfs tekst van een scherm.

De lus: nieuwe foto's in ~/amber-werk/fase2/beelden/ (daar legt
beelden.py ze per rit neer) worden beschreven in twee à drie Nederlandse
zinnen. De beschrijving gaat naar rapport/gezien.json (voor de pagina)
en als waarneming de brievenbus in — bron "beeld", dezelfde weg als
spraak: op een rungrens haar logboek in, nooit rechtstreeks.

**Slaapstand (Cleys punt, 13 aug):** de kaarten zijn het schaarst, de
472 GB RAM niet. Het model wordt in RAM geparkeerd en gaat alleen naar
kaart 1 wanneer er foto's liggen; na tien minuten zonder werk gaat het
terug. De mond blijft wél warm — een gesprek mag niet wachten, een foto
wel. Verhuizen kost ~3 s per kant.

Nakijken is hier niet: een beschrijving is geen som. do_sample=False
houdt het oog wel voorspelbaar: dezelfde foto geeft dezelfde tekst.
"""
import json
import os
import time

BEELDEN = "/home/arch/amber-werk/fase2/beelden"
GEZIEN_ADMIN = "/home/arch/oog/gezien.json"        # welke al bekeken zijn
UIT = "/home/arch/rapport/gezien.json"             # de laatste 20, zichtbaar
BRIEVENBUS = "/home/arch/amber-werk/fase1/brievenbus.jsonl"
SOORTEN = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif")
KAART = "cuda:1"
SLAAP_NA = 600            # tien minuten zonder werk → model terug naar RAM
VRAAG = ("Beschrijf in twee of drie korte Nederlandse zinnen wat je op "
         "deze foto ziet.")

import torch
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
from qwen_vl_utils import process_vision_info

model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2.5-VL-3B-Instruct",
    torch_dtype=torch.float16,        # fp16 om het geheugen, niet de snelheid
    attn_implementation="sdpa",       # geen flash-attn op Pascal
)
processor = AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-3B-Instruct")
plek = "cpu"                          # waar het model nu staat
laatste_werk = 0.0
print("oog wakker: Qwen2.5-VL 3B, geparkeerd in RAM", flush=True)


def naar(doel):
    global plek
    if plek == doel:
        return
    model.to(doel)
    if doel == "cpu":
        torch.cuda.empty_cache()      # geef kaart 1 echt terug aan de mond
    plek = doel
    print("oog verhuisd naar", doel, flush=True)


def kijk(pad):
    boodschap = [{"role": "user", "content": [
        {"type": "image", "image": pad,
         # begrens de kijkresolutie: foto's van een telefoon zijn groot en
         # het aantal beeldtokens groeit er rechtstreeks in mee
         "max_pixels": 1280 * 28 * 28},
        {"type": "text", "text": VRAAG}]}]
    tekst = processor.apply_chat_template(boodschap, tokenize=False,
                                          add_generation_prompt=True)
    beelden, _ = process_vision_info(boodschap)
    invoer = processor(text=[tekst], images=beelden,
                       return_tensors="pt").to(KAART)
    with torch.no_grad():
        uit = model.generate(**invoer, max_new_tokens=160, do_sample=False)
    uit = uit[:, invoer.input_ids.shape[1]:]
    beschrijving = processor.batch_decode(uit, skip_special_tokens=True)[0]
    beschrijving = beschrijving.strip()
    # liep de generatie tegen zijn plafond, kap dan op de laatste hele zin
    if len(beschrijving) > 40 and not beschrijving.endswith((".", "!", "?")):
        stukken = beschrijving.rsplit(".", 1)
        if len(stukken) == 2 and len(stukken[0]) > 40:
            beschrijving = stukken[0] + "."
    return beschrijving


def _lees(pad, anders):
    try:
        with open(pad) as f:
            return json.load(f)
    except Exception:
        return anders


def _schrijf(pad, inhoud):
    with open(pad + ".deel", "w") as f:
        json.dump(inhoud, f, ensure_ascii=False)
    os.replace(pad + ".deel", pad)


gezien = set(_lees(GEZIEN_ADMIN, []))
regels = _lees(UIT, {}).get("gezien") or []

while True:
    try:
        werk = []
        for rit in sorted(os.listdir(BEELDEN)):
            map_ = os.path.join(BEELDEN, rit)
            if not os.path.isdir(map_):
                continue
            for naam in sorted(os.listdir(map_)):
                sleutel = f"{rit}/{naam}"
                if naam.lower().endswith(SOORTEN) and sleutel not in gezien:
                    werk.append((rit, naam, os.path.join(map_, naam)))
        if werk:
            naar(KAART)
            laatste_werk = time.time()
        for rit, naam, pad in werk:
            print("kijkt naar:", f"{rit}/{naam}"[:70], flush=True)
            t0 = time.time()
            try:
                beschrijving = kijk(pad)
            except Exception as e:
                # één onleesbare foto (heic zonder codec, half bestand)
                # mag de rit niet ophouden — markeer en ga door
                print("oog-struikel over", naam[:50], ":", e, flush=True)
                gezien.add(f"{rit}/{naam}")
                _schrijf(GEZIEN_ADMIN, sorted(gezien))
                continue
            regels.append({"rit": rit, "bestand": naam[:64],
                           "tijd": time.strftime("%H:%M"),
                           "tekst": beschrijving})
            regels = regels[-20:]
            # eerst de brievenbus (liever dubbel dan kwijt), dan afvinken
            with open(BRIEVENBUS, "a") as f:
                f.write(json.dumps({
                    "tijd": time.time(),
                    "wanneer": time.strftime("%Y-%m-%d %H:%M"),
                    "bron": "beeld", "rit": rit, "bestand": naam[:64],
                    "tekst": beschrijving, "bezorgd": False,
                }, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            gezien.add(f"{rit}/{naam}")
            _schrijf(GEZIEN_ADMIN, sorted(gezien))
            _schrijf(UIT, {"gezien": regels})
            laatste_werk = time.time()
            print(f"gezien ({time.time() - t0:.0f} s):",
                  beschrijving[:70], flush=True)
        if plek != "cpu" and time.time() - laatste_werk > SLAAP_NA:
            naar("cpu")
    except Exception as e:
        print("oog-hapering:", e, flush=True)
        time.sleep(10)
    time.sleep(5)
