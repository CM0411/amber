"""Proef van het oog — Qwen2.5-VL 3B op kaart 1 (13 aug 2026).

Cleys volgorde: eerst dit model; werkt het niet, dan moondream; dan
Florence-2. De vraag die deze proef beantwoordt: draait Qwen2.5-VL op
torch 2.4.1 (Pascal, geen flash-attn, fp16 alleen voor het geheugen) en
komt er bruikbaar Nederlands uit?

Kaart 1 deelt hij met de mond; fp16 houdt hem klein genoeg.
"""
import sys
import time

import torch
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
from qwen_vl_utils import process_vision_info

KAART = "cuda:1"
VRAAG = ("Beschrijf in twee of drie korte Nederlandse zinnen wat je op "
         "deze foto ziet.")

t0 = time.time()
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2.5-VL-3B-Instruct",
    torch_dtype=torch.float16,        # fp16 om het geheugen, niet de snelheid
    attn_implementation="sdpa",       # geen flash-attn op Pascal
).to(KAART)
processor = AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-3B-Instruct")
print(f"geladen in {time.time() - t0:.0f} s, "
      f"{torch.cuda.memory_allocated(1) / 1e9:.1f} GB op kaart 1", flush=True)


def kijk(pad, vraag=VRAAG):
    boodschap = [{"role": "user", "content": [
        {"type": "image", "image": pad,
         # schermafbeeldingen zijn 5-14 MB; begrens de kijkresolutie zodat
         # het aantal beeldtokens (en het geheugen) beheersbaar blijft
         "max_pixels": 1280 * 28 * 28},
        {"type": "text", "text": vraag}]}]
    tekst = processor.apply_chat_template(boodschap, tokenize=False,
                                          add_generation_prompt=True)
    beelden, _ = process_vision_info(boodschap)
    invoer = processor(text=[tekst], images=beelden,
                       return_tensors="pt").to(KAART)
    t = time.time()
    with torch.no_grad():
        uit = model.generate(**invoer, max_new_tokens=120,
                             do_sample=False)
    uit = uit[:, invoer.input_ids.shape[1]:]
    antwoord = processor.batch_decode(uit, skip_special_tokens=True)[0]
    return antwoord.strip(), time.time() - t


if __name__ == "__main__":
    for pad in sys.argv[1:]:
        print("---", pad.rsplit("/", 1)[-1][:60])
        antwoord, duur = kijk(pad)
        print(f"({duur:.0f} s) {antwoord}", flush=True)
    print(f"piek kaart 1: {torch.cuda.max_memory_allocated(1) / 1e9:.1f} GB")
