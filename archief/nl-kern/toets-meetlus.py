"""
Toetst de meetlus.

De kernvraag: ziet deze meting het verschil tussen iets dat vergeet en iets dat
dat niet doet? Kan hij dat niet, dan meet hij niets, en dan is elk getal dat er
later uitkomt waardeloos — inclusief het getal waar dit hele project om draait.

Daarom twee namaakleerders met exact hetzelfde leerplan, waarvan er één per
constructie alles vergeet en de ander per constructie niets.

Draaien:  venv/bin/python kern/toets-meetlus.py
"""

import os
import shutil
import sys

import logboek
import meetlus
import namaakleerders
import taken

MAP = "/home/arch/amber-werk/tmp/meetlus"

geslaagd = 0
gefaald = 0


def toets(naam, goed, toelichting=""):
    global geslaagd, gefaald
    if goed:
        geslaagd += 1
        print(f"[  OK  ] {naam}")
    else:
        gefaald += 1
        print(f"[ FOUT ] {naam}")
    if toelichting:
        print(f"         {toelichting}")


print("=" * 70)
print("Toets — de meetlus")
print("=" * 70)
print()

# --- 1. Is de meetlat werkelijk afgeschermd? -------------------------------

print("--- Is de meetlat afgeschermd? ---")
stamper = namaakleerders.StampLeerder()
stamper.leer(taken.leerreeks("rekenen", 1, 500))
toets(
    "wie de leertaken uit zijn hoofd leert scoort nul op de meetlat",
    meetlus.meet(stamper, "rekenen", 1) == 0.0,
    f"{len(stamper.tabel)} opgaven ingestampt, en toch nul — de meetlat is dus "
    f"werkelijk ongezien",
)

# En andersom: kent hij de meetlat wél, dan scoort hij vol. Zonder deze
# tegenproef bewijst het bovenstaande niets — een leerder die altijd nul
# scoort zou er ook doorheen komen.
kenner = namaakleerders.StampLeerder()
kenner.leer(taken.testverzameling("rekenen", 1, 100))
toets("wie de meetlat wél kent scoort vol",
      meetlus.meet(kenner, "rekenen", 1) == 1.0,
      "tegenproef: de meting kán dus wel hoog uitvallen")

print()

# --- 2. Meten mag niet leren -----------------------------------------------

print("--- Meten verandert niets ---")
leerder = namaakleerders.EenRegelLeerder()
leerder.leer(taken.leerreeks("rekenen", 3, 200))
eerste = meetlus.meet(leerder, "rekenen", 3)
tweede = meetlus.meet(leerder, "rekenen", 3)
derde = meetlus.meet(leerder, "rekenen", 3)
toets("drie keer meten geeft drie keer dezelfde score",
      eerste == tweede == derde, f"{eerste:.0%} telkens")

print()

# --- 3. Waar het om draait: ziet de meting vergeten? -----------------------

print("--- Vergeet-ie? ---")
print("  Twee leerders, hetzelfde plan: eerst rekenen graad 1, dan rekenen graad 3.")
print()

plan = [("rekenen", 1), ("rekenen", 3)]

shutil.rmtree(MAP, ignore_errors=True)
os.makedirs(MAP, exist_ok=True)
log = logboek.Logboek(f"{MAP}/logboek.jsonl")

vergeetachtig = meetlus.c_meting(namaakleerders.EenRegelLeerder(), plan, log=log)
degelijk = meetlus.c_meting(namaakleerders.RegelPerSoortLeerder(), plan, log=log)
log.sluit()

r1 = vergeetachtig["vergeten"][0]        # rekenen graad 1, bij de vergeetachtige
r2 = degelijk["vergeten"][0]             # rekenen graad 1, bij de degelijke

print("  Eén regel voor alles:")
print("  " + meetlus.tabel(vergeetachtig).replace("\n", "\n  "))
print()
print("  Een regel per soort:")
print("  " + meetlus.tabel(degelijk).replace("\n", "\n  "))
print()

toets(
    "allebei leren ze graad 1 werkelijk",
    r1["winst"] > 0.4 and r2["winst"] > 0.4,
    f"winst {r1['winst']:.0%} en {r2['winst']:.0%} — zonder winst zegt "
    f"vergeten niets. Rond de 50% is hier het plafond: rekenen graad 1 kent "
    f"vier vormen en deze leerders onthouden maar één regel",
)
toets(
    "de leerder met één regel verliest graad 1 als hij graad 3 leert",
    r1["behouden"] is not None and r1["behouden"] < 0.1,
    f"behouden: {r1['behouden']:.0%}",
)
toets(
    "de leerder met een regel per soort verliest niets",
    r2["behouden"] is not None and r2["behouden"] > 0.95,
    f"behouden: {r2['behouden']:.0%}",
)
toets(
    "de meting ziet dus het verschil tussen vergeten en niet vergeten",
    r2["behouden"] - r1["behouden"] > 0.8,
    "dit is de eigenschap waar alles op steunt; zonder dit meet C niets",
)

print()

# --- 4. Niets geleerd is geen vergeten -------------------------------------

print("--- Waar niets geleerd is ---")
code_regels = [r for r in vergeetachtig["metingen"][-1]["scores"] if r[0] == "code"]
toets("de familie code is meegemeten", len(code_regels) == len(taken.GRADEN))

# Graad 5 en niet graad 1: `a = X / b = Y / print(a + b)` is een optelsom in
# vermomming, en die pakken deze regeltjes gewoon. Graad 5 is een functie in een
# lus en daar komt geen regel over de losse getallen bij in de buurt.
alleen_code = meetlus.c_meting(namaakleerders.EenRegelLeerder(), [("code", 5)])
rc = alleen_code["vergeten"][0]
toets(
    "zonder winst wordt er geen 'behouden' verzonnen",
    rc["winst"] <= 1e-9 and rc["behouden"] is None,
    "je kunt niet vergeten wat je nooit geleerd hebt — dan liever niets dan "
    "een getal dat nergens op slaat",
)

print()

# --- 5. Alles wordt gemeten, niet alleen wat net geleerd is ----------------

print("--- Wat er gemeten wordt ---")
alles = vergeetachtig["metingen"][0]["scores"]
toets("elke familie en graad komt in elke meting voor",
      len(alles) == len(taken.FAMILIES) * len(taken.GRADEN),
      f"{len(alles)} combinaties per fase — de vraag is juist wat er met de "
      f"rest gebeurt")
toets("er is een meting vóór het leren en na elke stap",
      len(vergeetachtig["metingen"]) == len(plan) + 1)

print()

# --- 6. De metingen staan in het logboek -----------------------------------

print("--- Vastgelegd ---")
regels, _ = logboek.lees(f"{MAP}/logboek.jsonl")
metingen = [r for r in regels if r["soort"] == "meting"]
toets(
    "elke meting is weggeschreven",
    len(metingen) == 2 * (len(plan) + 1),
    f"{len(metingen)} regels — uitkomsten die je niet opnieuw wilt verdienen",
)
toets("en de scores staan erin", "rekenen/1" in metingen[-1]["scores"])

shutil.rmtree(MAP, ignore_errors=True)

print()
print("=" * 70)
print(f"geslaagd: {geslaagd}    gefaald: {gefaald}")
print("=" * 70)
sys.exit(0 if gefaald == 0 else 1)
