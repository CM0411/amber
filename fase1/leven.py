"""
Leven in de wereld — zelf kiezen, en periodiek proefwerk.

Dit is voor het eerst de lus zoals hij bedoeld is: ze kiest zelf waar ze aan
werkt, haalt haar stof uit de grammatica in plaats van uit de catalogus, en de
wereld gaat een stap dieper open zodra ze de huidige rand aankan.

Elke stap is: kies een onderwerp, probeer een partij taken, onthoud wat het
was, leer ervan. Dat proberen kost ongeveer twee derde van de tijd per stap —
ze moet immers eerst antwoorden voordat er iets na te kijken valt. Dat is de
prijs van "wat ze zonder opdracht doet is het signaal": zonder een poging weet
niemand waar ze staat.

Om de zoveel stappen worden de drie proefwerken afgenomen. Daar wordt nooit op
geoefend — `wereld.leerreeks` sluit die opgaven uit.

Draaien:  venv/bin/python fase1/leven.py [stappen]
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "kern"))

import determinisme                        # MOET vóór torch
determinisme.zet_vast(20260808)

import checkpoint
import logboek
import proefwerken
from leren import Leerder

STAPPEN = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
PROEFWERK_ELKE = 500
OPGAVEN_PER_PROEFWERK = 150
MAP = "/home/arch/amber-werk/fase1/leven"
VERSLAG = "/home/arch/amber-werk/fase1/leven.md"

os.makedirs(MAP, exist_ok=True)
log = logboek.Logboek(f"{MAP}/logboek.jsonl")
leerder = Leerder(partij=64)

# --- hervatten -------------------------------------------------------------
# Waar alles omheen gebouwd is: de server kan 's nachts uitvallen door warmte,
# en dan hoort ze verder te gaan waar ze was in plaats van overnieuw te
# beginnen. Zonder dit is een nacht doorwerken één crash van niets waard.

BEGIN = 1
OPNAME = f"{MAP}/momentopname.pt"
if os.path.exists(OPNAME):
    inhoud = checkpoint.lees(OPNAME, apparaat=leerder.apparaat)
    BEGIN = checkpoint.herstel(inhoud, leerder.kern, leerder.optimizer,
                               leerder.apparaat) + 1
    leerder.stappen = BEGIN - 1
    extra = inhoud.get("extra") or {}
    if "geheugen" in extra:
        leerder.zet_terug(extra)
        print(f"  geheugen terug: {len(leerder.geheugen):,} herinneringen")
    else:
        # opname van vóór 9 aug 2026: alleen diepte en scores, geen geheugen
        if extra.get("diepste_per"):
            leerder.diepste_per = dict(extra["diepste_per"])
            for f, d in leerder.diepste_per.items():
                for i in range(1, d + 1):
                    leerder.nieuwsgierig.voeg_toe((f, i), BEGIN)
        for sleutel, score in (extra.get("scores") or {}).items():
            f, d = sleutel.rsplit("/", 1)
            leerder.nieuwsgierig.bijgewerkt((f, int(d)), score, BEGIN)

    toestand = logboek.hervat(MAP, tot_stap=BEGIN)
    gat = toestand["gat_seconden"]
    print(f"HERVAT bij stap {BEGIN}. Vorige keer eindigde met "
          f"'{toestand['stilte']}'"
          + (f", {gat / 60:.0f} minuten geleden." if gat else "."))
    log.schrijf("hervat", stap=BEGIN, stilte=toestand["stilte"],
                gat_seconden=gat)

print("=" * 72)
print("Leven in de wereld")
print("=" * 72)
print(f"{leerder.kern.aantal_parameters():,} parameters op {leerder.apparaat}")
print(f"{STAPPEN} stappen, herhaling {leerder.herhaling:.1%}, "
      f"wereld open tot diepte {leerder.diepste}")
print(f"proefwerk elke {PROEFWERK_ELKE} stappen, "
      f"{OPGAVEN_PER_PROEFWERK} opgaven per stuk\n")


def proefwerk(stap):
    scores = proefwerken.neem(leerder, hoogstens=OPGAVEN_PER_PROEFWERK)
    log.schrijf("proefwerk", stap=stap, scores=scores,
                diepste=leerder.diepste)
    return scores


metingen = [(0, proefwerk(0), leerder.diepste)]
print(f"  stap {0:>5} | " + "  ".join(f"{n} {v:>4.0%}"
                                      for n, v in sorted(metingen[0][1].items())))

begin = time.perf_counter()
gekozen = {}
for stap in range(BEGIN, STAPPEN + 1):
    uit = leerder.werk(stap)
    gekozen[(uit["familie"], uit["diepte"])] = \
        gekozen.get((uit["familie"], uit["diepte"]), 0) + 1
    log.schrijf("stap", stap=stap, familie=uit["familie"],
                diepte=uit["diepte"], score=uit["score"], fout=uit["fout"])
    if uit["dieper"]:
        print(f"  stap {stap:>5} | wereld open: "
              + ", ".join(f"{f} tot {d}" for f, d in uit["dieper"]))
        log.schrijf("wereld_dieper", stap=stap, diepste_per=uit["diepste_per"])

    # Elke 50 stappen een teken van leven: hoever, hoe snel, hoelang nog.
    if stap % 50 == 0:
        verstreken = time.perf_counter() - begin
        per_stap = verstreken / (stap - BEGIN + 1)
        nog = (STAPPEN - stap) * per_stap
        laatste_score = ("--" if uit["score"] is None
                         else f"{uit['score']:.0%}")
        print(f"  {time.strftime('%H:%M')}  stap {stap:>6}/{STAPPEN}"
              f"  {stap / STAPPEN:>4.0%}"
              f"  {per_stap * 1000:>4.0f} ms/st"
              f"  nog {int(nog // 3600)}u{int(nog % 3600 // 60):02d}m"
              f"   {uit['familie']}/{uit['diepte']}  {laatste_score:>4}",
              flush=True)

    if stap % PROEFWERK_ELKE == 0:
        scores = proefwerk(stap)
        metingen.append((stap, scores, leerder.diepste))
        verstreken = time.perf_counter() - begin
        print(f"  stap {stap:>5} | "
              + "  ".join(f"{n} {v:>4.0%}" for n, v in sorted(scores.items()))
              + f"   | diepte tot {leerder.diepste}"
              + f" | {verstreken / stap * 1000:.0f} ms/stap")
        checkpoint.schrijf(
            OPNAME, stap, leerder.kern, leerder.optimizer,
            determinisme.stand(),
            extra=leerder.neem_mee())
        log.schoon_op(stap)

log.rust(stap=STAPPEN, reden="leven klaar")
log.sluit()

# --- verslag ---------------------------------------------------------------

namen = sorted(metingen[0][1])
kop = ("| stap | " + " | ".join(f"proefwerk {n}" for n in namen)
       + " | wereld open tot |")
regels = [kop, "|---:|" + "---:|" * (len(namen) + 1)]
for stap, scores, diepste in metingen:
    regels.append(f"| {stap} | "
                  + " | ".join(f"{scores[n]:.0%}" for n in namen)
                  + f" | diepte {diepste} |")
tabel = "\n".join(regels)

print("\n" + "=" * 72)
print(tabel)
print("=" * 72)
print(f"\nWereld open tot diepte {leerder.diepste}. "
      f"Geheugen: {len(leerder.geheugen)} herinneringen.")

vaakst = sorted(gekozen.items(), key=lambda x: -x[1])[:6]
print("\nWaar ze zelf voor koos, de zes vaakst gekozen onderwerpen:")
for (familie, diepte), aantal in vaakst:
    print(f"  {familie}/{diepte}: {aantal}× ({aantal / STAPPEN:.0%})")

with open(VERSLAG, "w") as f:
    f.write("# Leven in de wereld\n\n")
    f.write(f"{STAPPEN} stappen, herhaling {leerder.herhaling:.1%}, "
            f"partij {leerder.partij}. Ze kiest zelf waar ze aan werkt.\n\n")
    f.write("## Proefwerken over de tijd\n\n" + tabel + "\n\n")
    f.write(f"Wereld open tot diepte {leerder.diepste} "
            f"(begonnen bij 3).\n\n## Waar ze zelf voor koos\n\n")
    for (familie, diepte), aantal in vaakst:
        f.write(f"- {familie}/{diepte}: {aantal}× ({aantal / STAPPEN:.0%})\n")
    f.flush()
    os.fsync(f.fileno())
print(f"\nVerslag: {VERSLAG}")
