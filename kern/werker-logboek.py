"""
Werker voor de logboektoets.

Bootst na wat er 's nachts gebeurt: doorwerken, af en toe een momentopname, en
dan óf netjes afsluiten óf er middenin doodvallen.

  werker-logboek.py val_om     tot stap 87, dan SIGKILL op zichzelf
  werker-logboek.py netjes     tot stap 87, dan een nette afsluiting
  werker-logboek.py hervat     opstarten en melden wat er gevonden is

SIGKILL op de eigen procesnummer is het eerlijkste model van stroomverlies dat
je in een toets kunt krijgen: geen opruimen, geen flush, geen afhandelaar die
er nog iets van maakt. En het is exact getimed, dus de toets is herhaalbaar.
"""

import determinisme                       # MOET vóór torch
determinisme.zet_vast(1234)

import json
import os
import signal
import sys

import torch

import checkpoint
import logboek

MAP = "/home/arch/amber-werk/tmp/logboektoets"
OPNAME = f"{MAP}/momentopname.pt"
OPNAME_BIJ = 50          # zo vaak is een volledige opname te duur
OMVALLEN_BIJ = 87
EIND = 120


def bouw():
    determinisme.begin_stap(0)
    model = torch.nn.Linear(8, 4)
    return model, torch.optim.SGD(model.parameters(), lr=0.1)


def main():
    modus = sys.argv[1]
    os.makedirs(MAP, exist_ok=True)
    model, optimizer = bouw()

    if modus == "hervat":
        stap = 0
        if os.path.exists(OPNAME):
            inhoud = checkpoint.lees(OPNAME)
            stap = checkpoint.herstel(inhoud, model, optimizer)
        toestand = logboek.hervat(MAP, tot_stap=stap)
        print(json.dumps({
            "opname_bij": stap,
            "gebeurtenissen_na_opname": len(toestand["gebeurtenissen"]),
            "eerste_na_opname": (toestand["gebeurtenissen"][0]["stap"]
                                 if toestand["gebeurtenissen"] else None),
            "laatste_na_opname": (toestand["gebeurtenissen"][-1].get("stap")
                                  if toestand["gebeurtenissen"] else None),
            "stilte": toestand["stilte"],
            "gat_gemeten": toestand["gat_seconden"] is not None,
            "waarnemingen": [g["tekst"] for g in toestand["gebeurtenissen"]
                             if g["soort"] == "waarneming"],
        }))
        return

    # fsync na elke regel: maakt de toets herhaalbaar in plaats van afhankelijk
    # van waar de tussenpoos toevallig viel.
    log = logboek.Logboek(f"{MAP}/logboek.jsonl", fsync_tussenpoos=0)

    for stap in range(EIND):
        determinisme.begin_stap(stap)
        x = torch.randn(4, 8)
        verlies = model(x).pow(2).mean()
        optimizer.zero_grad()
        verlies.backward()
        optimizer.step()

        log.schrijf("stap", stap=stap, verlies=verlies.item().hex())

        # Iets wat van buiten kwam en dus nergens uit terug te rekenen is.
        if stap == 60:
            log.schrijf("waarneming", stap=stap, bron="cley",
                        tekst="dit is niet af te leiden uit het zaad")

        if stap + 1 == OPNAME_BIJ:
            checkpoint.schrijf(OPNAME, stap + 1, model, optimizer,
                               determinisme.stand())
            # Pas ná een geslaagde opname opschonen. Gaat het daartussen mis,
            # dan filtert hervat() op stapnummer en kan er niets dubbel.
            log.schoon_op(stap + 1)

        if modus == "val_om" and stap == OMVALLEN_BIJ:
            log._naar_schijf()
            os.kill(os.getpid(), signal.SIGKILL)     # stroom eraf

    if modus == "netjes":
        log.rust(stap=EIND - 1, reden="Cley gaat weg")
        log.sluit()
        print(json.dumps({"modus": "netjes", "tot": EIND}))


if __name__ == "__main__":
    main()
