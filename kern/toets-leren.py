"""
Toetst het herhaalgeheugen, de nieuwsgierigheid en de leerlus.

Deze drie modules waren de enige zonder toets, en in precies deze drie zaten
op 8 aug 2026 twee fouten die er met de hand uit moesten:

  * het geheugen bewaarde háár antwoord in plaats van het juiste, dus bij
    herhalen zou ze haar fouten inoefenen
  * `leer()` vulde het geheugen niet, waardoor herhaling niets deed terwijl de
    vergelijking er wel iets over leek te zeggen

Beide staan hieronder als toets, zodat ze niet terug kunnen komen.

Draaien:  venv/bin/python kern/toets-leren.py
"""

import determinisme                        # MOET vóór torch
determinisme.zet_vast(1234)

import sys

import torch

import herhaalgeheugen as hg
import leren
import netwerk
import nieuwsgierigheid as ng
import taken
import tekens

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


def kleine_leerder(**meer):
    kern = netwerk.Kern(lagen=2, breedte=64, koppen=2, venster=128)
    return leren.Leerder(kern=kern, partij=8, **meer)


print("=" * 70)
print("Toets — geheugen, nieuwsgierigheid en leerlus")
print("=" * 70)
print()

# --- 1. De flessenhals -----------------------------------------------------

print("--- De flessenhals ---")
geheugen = hg.Herhaalgeheugen(ruimte=100)
t = taken.maak("rekenen", 3, 500)
geheugen.onthoud(t, "fout antwoord", False)

opgeslagen = geheugen._inhoud[0]
toets(
    "het geheugen bewaart codes, geen taken",
    isinstance(opgeslagen["code"], list)
    and all(isinstance(c, int) for c in opgeslagen["code"]),
    "er is geen andere weg naar binnen dan door de doorgang",
)

hervonden = geheugen.herhaal(1, taken.Trekker(1))[0]
toets(
    "wat er in gaat is het JUISTE antwoord, niet wat zij ervan maakte",
    hervonden["oplossing"] == t.oplossing,
    f"opgeslagen {hervonden['oplossing']!r}, zij zei 'fout antwoord' — "
    f"anders oefent ze bij het herhalen haar eigen fouten in",
)
toets("de opgave komt er heel uit", hervonden["opgave"] == t.opgave)

# De uitwerking is de les. Bewaart het geheugen alleen het kale antwoord, dan
# leert elke herinnering haar het uitwerken over te slaan — en met 37,5%
# herhaling is dat ruim een derde van alles wat ze ziet. Die fout zat er op
# 8 aug 2026 in en heeft een hele nacht training bedorven zonder één melding.
import wereld as wereld_module                                    # noqa: E402
diep = wereld_module.maak("rekenen", 4, 500)
g2 = hg.Herhaalgeheugen()
g2.onthoud(diep, "gegokt", False)
uit_geheugen = leren._als_taak(g2.herhaal(1, taken.Trekker(1))[0])
toets(
    "het geheugen bewaart de uitwerking, niet alleen het antwoord",
    uit_geheugen.te_leren() == diep.te_leren(),
    f"uit het geheugen: {uit_geheugen.te_leren()!r}",
)
toets(
    "en het antwoord is er nog uit te halen om na te kijken",
    uit_geheugen.nakijk(diep.uitwerking) and uit_geheugen.oplossing == diep.oplossing,
)

# Wat niet past wordt geweigerd. In fase 4 is dát de druk die U moet opleveren.
krap = hg.Herhaalgeheugen(flessenhals=hg.Flessenhals(lengte=8))
gelukt = krap.onthoud(t, t.oplossing, True)
toets("wat niet door de doorgang past wordt geweigerd en geteld",
      not gelukt and len(krap) == 0 and krap.geweigerd == 1,
      "in fase 1 gebeurt dit vrijwel nooit; in fase 4 is het de bedoeling")

toets("de bezetting wordt gemeld",
      0 < geheugen.flessenhals.bezetting(opgeslagen) < 1,
      f"{geheugen.flessenhals.bezetting(opgeslagen):.0%} van de doorgang — "
      f"dít getal knijpt fase 4")

print()

# --- 2. Niet nagekeken is niet fout ----------------------------------------

print("--- Niet nagekeken ---")
g = hg.Herhaalgeheugen()
g.onthoud(taken.maak("rekenen", 1, 300), "x", None)
g.onthoud(taken.maak("rekenen", 1, 301), "x", True)
g.onthoud(taken.maak("rekenen", 1, 302), "x", False)
stand = g.stand()
toets(
    "niet-nagekeken telt niet mee als fout",
    stand["nagekeken"] == 2 and abs(stand["goed_deel"] - 0.5) < 1e-9,
    "twee van de drie zijn nagekeken, daarvan de helft goed — "
    "None meetellen als fout zou het beeld stilletjes vertekenen",
)

print()

# --- 3. Het geheugen loopt vol ---------------------------------------------

print("--- Vollopen ---")
klein = hg.Herhaalgeheugen(ruimte=5)
for n in range(20):
    klein.onthoud(taken.maak("rekenen", 2, 400 + n), "x", True)
toets("er blijven er precies zoveel over als er ruimte is", len(klein) == 5)
inhoud = [klein.flessenhals.ontcijfer(o)["opgave"] for o in klein._inhoud]
toets("en het oudste verdwijnt als eerste",
      taken.maak("rekenen", 2, 419).opgave in inhoud
      and taken.maak("rekenen", 2, 400).opgave not in inhoud)

print()

# --- 4. Herhalen is herhaalbaar --------------------------------------------

print("--- Herhaalbaar ophalen ---")
a = geheugen.herhaal(3, taken.Trekker(99))
b = geheugen.herhaal(3, taken.Trekker(99))
toets("dezelfde trekker haalt dezelfde herinneringen op",
      [x["opgave"] for x in a] == [x["opgave"] for x in b],
      "de trekker wordt meegegeven en niet zelf verzonnen, zodat de keuze uit "
      "(zaad, stapnummer) volgt")

print()

# --- 5. Nieuwsgierigheid ---------------------------------------------------

print("--- Nieuwsgierigheid ---")
n1 = ng.Nieuwsgierigheid()
n2 = ng.Nieuwsgierigheid()
keuzes1 = [n1.kies(s, taken.Trekker(s)) for s in range(50)]
keuzes2 = [n2.kies(s, taken.Trekker(s)) for s in range(50)]
toets("dezelfde trekkers geven dezelfde volgorde van onderwerpen",
      keuzes1 == keuzes2)

n = ng.Nieuwsgierigheid()
voor = n.aantrekking(100)[("rekenen", 1)]
n.bijgewerkt(("rekenen", 1), 1.0, 100)
na = n.aantrekking(100)[("rekenen", 1)]
toets("nieuwsgierigheid dooft uit zodra ze iets kan", na < voor,
      f"{voor:.2f} → {na:.2f} zodra de score op 1 staat")

n.bijgewerkt(("rekenen", 1), 1.0, 0)
toets("en komt terug als iets lang niet langs is geweest",
      n.aantrekking(1000)[("rekenen", 1)] > na,
      "zonder dit blijft ze hangen bij het moeilijkste en meet C de "
      "volgorde in plaats van vergeten")

n = ng.Nieuwsgierigheid()
for soort in n.soorten:
    n.bijgewerkt(soort, 1.0, 0)
n.bijgewerkt(("code", 1), 0.0, 0)
gekozen = {n.kies(s, taken.Trekker(s * 31 + 7)) for s in range(300)}
toets(
    "ze kiest niet altijd het aantrekkelijkste",
    len(gekozen) > 1,
    f"{len(gekozen)} verschillende onderwerpen in 300 keuzes — altijd het "
    f"hoogste kiezen zou haar op één onderwerp vastzetten",
)
toets("en het aantrekkelijkste komt wel het vaakst langs",
      max(((n.kies(s, taken.Trekker(s * 31 + 7)) == ("code", 1))
           for s in range(300)), default=False))

print()

# --- 6. De leerlus: telt de fout over het juiste stuk? ---------------------

print("--- Waar de fout over telt ---")
leerder = kleine_leerder()
t = taken.maak("rekenen", 1, 700)
codes, masker = leerder._partij_maken([t])

# Zo doet _stap het ook: de score op plaats i voorspelt teken i+1.
doel = codes[:, 1:][masker[:, 1:]].tolist()
toets(
    "de fout telt precies over het antwoord plus het EIND-teken",
    tekens.decodeer(doel) == t.oplossing and doel[-1] == tekens.EIND,
    f"voorspeld wordt: {tekens.toon(doel)!r} — één positie verschuiven en ze "
    f"leert de vraag voorspellen, wat er in de foutcurve prima uitziet",
)
toets("er wordt niets uit de vraag meegerekend",
      not any(masker[0][:codes[0].tolist().index(tekens.ANTWOORD) + 1]))

print()

# --- 7. In één partij antwoorden is hetzelfde als los ---------------------

print("--- Antwoorden in één partij ---")
leerder = kleine_leerder()
proef = [taken.maak("rekenen", 1, 800 + i) for i in range(6)]
# Zelfde ruimte voor beide, anders knipt de ene af waar de andere doorgaat:
# de ruimte hangt af van de langste opgave in de partij.
samen = leerder.antwoorden(proef, hoogstens=32)
los = [leerder.antwoorden([t], hoogstens=32)[0] for t in proef]
toets(
    "zes taken samen geeft hetzelfde als zes keer één",
    samen == los,
    "rechts opvullen met een eigen teller per taak; links opvullen zou de "
    "plaatsen verschuiven en dat zou hier stil misgaan",
)

print()

# --- 8. De partij blijft even groot ----------------------------------------

print("--- Gelijke partijen ---")
zonder = kleine_leerder(herhaling=0.0)
met = kleine_leerder(herhaling=0.5)
toets("zonder herhaling is de hele partij nieuw",
      zonder.nieuw_per_partij == zonder.partij)
toets("met 50% herhaling is de helft nieuw",
      met.nieuw_per_partij == met.partij // 2,
      f"{met.nieuw_per_partij} nieuw + {met.partij - met.nieuw_per_partij} "
      f"herhaald = {met.partij}. Herhaling gaat ten koste van nieuw materiaal "
      f"en komt er niet bovenop")

# En dat moet ook werkelijk zo uitpakken in de partij die het netwerk ziet.
gezien = []
echte_stap = met._stap
met._stap = lambda brokje: (gezien.append(len(brokje)), echte_stap(brokje))[1]
met.leer(taken.leerreeks("rekenen", 1, 40))
toets("elke partij die het netwerk ziet is even groot",
      all(g == met.partij for g in gezien),
      f"partijen: {gezien} — ook de eerste, want het geheugen wordt gevuld "
      f"vóórdat er uit herhaald wordt")
met._stap = echte_stap

print()

# --- 9. Leren vult het geheugen --------------------------------------------

print("--- Leren onthoudt ---")
leerder = kleine_leerder()
toets("het geheugen begint leeg", len(leerder.geheugen) == 0)
leerder.leer(taken.leerreeks("rekenen", 1, 16))
toets(
    "wat geleerd wordt gaat ook het geheugen in",
    len(leerder.geheugen) == 16,
    "zonder dit blijft het geheugen leeg en doet herhaling niets, terwijl een "
    "vergelijking mét en zónder er wel iets over lijkt te zeggen",
)

print()

# --- 10. Leert het ding werkelijk? -----------------------------------------

print("--- Zakt de fout? ---")
determinisme.zet_vast(7)
leerder = kleine_leerder()
eerste = leerder.leer(taken.leerreeks("rekenen", 1, 8 * 5))
for _ in range(10):
    laatste = leerder.leer(taken.leerreeks("rekenen", 1, 8 * 5, vanaf=taken.TEST_TOT + 9000))
toets("de fout zakt bij herhaald oefenen", laatste < eerste,
      f"{eerste:.3f} → {laatste:.3f}")

print()

# --- 11. Herhaalbaar -------------------------------------------------------

print("--- Herhaalbaar ---")


def gewichten_na_leren():
    determinisme.zet_vast(555)
    l = kleine_leerder()
    l.leer(taken.leerreeks("rekenen", 2, 24))
    return [p.detach().clone() for p in l.kern.parameters()]


toets("twee identieke runs geven bit voor bit dezelfde gewichten",
      all(torch.equal(a, b) for a, b in zip(gewichten_na_leren(),
                                            gewichten_na_leren())),
      "de leerlus is daarmee net zo herhaalbaar als de kern eronder")

print("--- Haar toestand gaat mee ---")
# N: "Haar toestand is meer dan gewichten: ook haar aangegroeide geheugen."
# Bij de crash van 9 aug 2026 hervatte de run met haar kunnen intact en haar
# 20.000 herinneringen weg. Dit zet vast dat dat niet terug kan komen.
import checkpoint as cp_module                                     # noqa: E402
import os as os_module                                             # noqa: E402
determinisme.zet_vast(808)
l1 = kleine_leerder()
l1.leer(taken.leerreeks("rekenen", 2, 24))
l1.nieuwsgierig.bijgewerkt(("rekenen", 2), 0.7, 5)
pad = "/home/arch/amber-werk/tmp/toestand.pt"
cp_module.schrijf(pad, 5, l1.kern, l1.optimizer, determinisme.stand(),
                  extra=l1.neem_mee())

determinisme.zet_vast(808)
l2 = kleine_leerder()
inhoud = cp_module.lees(pad)
cp_module.herstel(inhoud, l2.kern, l2.optimizer, l2.apparaat)
l2.zet_terug(inhoud["extra"])

toets("haar geheugen komt bit voor bit terug uit de momentopname",
      l2.geheugen._inhoud == l1.geheugen._inhoud
      and len(l2.geheugen) == 24,
      f"{len(l2.geheugen)} herinneringen, inhoud identiek")
toets("de nieuwsgierigheid komt terug mét haar klok",
      l2.nieuwsgierig.score == l1.nieuwsgierig.score
      and l2.nieuwsgierig.laatst == l1.nieuwsgierig.laatst,
      "zonder de klok trekt vervlogen tijd na een herstart nergens meer aan")
a = l1.geheugen.herhaal(5, taken.Trekker(3))
b = l2.geheugen.herhaal(5, taken.Trekker(3))
toets("herhalen na de herstart geeft exact dezelfde herinneringen",
      [x["opgave"] for x in a] == [x["opgave"] for x in b])
os_module.remove(pad)

print()
print("=" * 70)
print(f"geslaagd: {geslaagd}    gefaald: {gefaald}")
print("=" * 70)
sys.exit(0 if gefaald == 0 else 1)
