"""
Een piepklein leerlusje, alleen om de toets echt te maken.

Draait als los proces, zodat "herstarten" ook werkelijk een nieuw proces is en
niet een hergebruikte Python met warme toestand in het geheugen. Dat verschil is
het hele punt: een lus die binnen één proces herstart bewijst niets over wat er
gebeurt als de server 's nachts uitvalt.

  werker.py doorlopen   0 t/m 100 achter elkaar
  werker.py deel1       0 t/m 50, dan checkpoint schrijven en stoppen
  werker.py deel2       checkpoint lezen, 50 t/m 100
"""

import determinisme                       # MOET vóór torch
determinisme.zet_vast(1234)

import hashlib
import json
import sys

import torch

import checkpoint

EIND = 100
HALF = 50
MAP = "/home/arch/amber-werk/tmp"
PAD = f"{MAP}/toets-checkpoint.pt"

apparaat = "cuda" if torch.cuda.is_available() else "cpu"


def bouw():
    """Vaste opbouw. Na zet_vast() is de beginstand van de gewichten bepaald."""
    determinisme.begin_stap(0)
    model = torch.nn.Sequential(
        torch.nn.Linear(16, 32),
        torch.nn.ReLU(),
        torch.nn.Linear(32, 4),
    ).to(apparaat)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.05, momentum=0.9)
    return model, optimizer


def vingerafdruk(model):
    """Eén getal over alle gewichten, in vaste sleutelvolgorde.

    Sorteren is nodig: zonder vaste volgorde hangt de uitkomst af van de
    volgorde van het woordenboek en vergelijk je niet wat je denkt.
    """
    h = hashlib.sha256()
    for sleutel in sorted(model.state_dict()):
        h.update(sleutel.encode())
        h.update(model.state_dict()[sleutel].detach().cpu().numpy().tobytes())
    return h.hexdigest()


def stap_doen(model, optimizer, stap):
    determinisme.begin_stap(stap)
    x = torch.randn(32, 16, device=apparaat)
    doel = torch.randn(32, 4, device=apparaat)
    verlies = ((model(x) - doel) ** 2).mean()
    optimizer.zero_grad()
    verlies.backward()
    optimizer.step()
    # Als hexadecimaal, want dan vergelijk je de bits en niet een afronding.
    return verlies.detach().cpu().item().hex()


def main():
    modus = sys.argv[1]
    model, optimizer = bouw()

    begin = 0
    verliezen = []

    if modus == "deel2":
        inhoud = checkpoint.lees(PAD, apparaat=apparaat)
        begin = checkpoint.herstel(inhoud, model, optimizer, apparaat)

    einde = HALF if modus == "deel1" else EIND
    for stap in range(begin, einde):
        verliezen.append(stap_doen(model, optimizer, stap))

    if modus == "deel1":
        checkpoint.schrijf(PAD, einde, model, optimizer, determinisme.stand())

    print(json.dumps({
        "modus": modus,
        "van": begin,
        "tot": einde,
        "verliezen": verliezen,
        "vingerafdruk": vingerafdruk(model),
    }))


if __name__ == "__main__":
    main()
