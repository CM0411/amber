"""
Toetst de wereld en de proefwerken.

De twee dingen die hier het zwaarst wegen:

  * **diepte moet werkelijk moeilijker maken**, niet alleen langer. De eerste
    opzet had een "tweede orde"-regel die de regel eronder negeerde, waardoor
    diepte 5 en 8 vrijwel dezelfde rij gaven. Dat is een vlag die eroverheen
    hangt, geen stapeling
  * **niets uit de wereld mag met een proefwerk botsen** — niet op nummer en
    niet op tekst. Bij `taken.py` bleek dat een kwart van de leerstof te zijn

Draaien:  venv/bin/python kern/toets-wereld.py
"""

import contextlib
import io
import re
import sys

import proefwerken
import taken
import wereld

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
print("Toets — de wereld en de proefwerken")
print("=" * 70)
print()

# --- 1. Kloppen de antwoorden? ---------------------------------------------
# Voor rekenen en code is er een onafhankelijke bron: Python zelf.

print("--- Kloppen de antwoorden? ---")
fout = []
for diepte in range(2, 13):
    for n in range(60):
        t = wereld.maak("rekenen", diepte, n)
        if str(eval(t.opgave)) != t.oplossing:
            fout.append(t.opgave)
toets("660 uitdrukkingen komen overeen met wat Python zelf uitrekent",
      not fout, f"{len(fout)} afwijkingen" if fout else "geen enkele afwijking")

fout = []
for diepte in range(1, 13):
    for n in range(25):
        t = wereld.maak("code", diepte, n)
        uit = io.StringIO()
        with contextlib.redirect_stdout(uit):
            exec(t.opgave, {})
        if uit.getvalue().strip() != t.oplossing:
            fout.append(t.opgave)
toets("300 programma's drukken werkelijk af wat als antwoord genoteerd staat",
      not fout, "elk programma echt uitgevoerd")

# Bij de rijen is er geen tweede bron van waarheid. Wel is de eenvoudigste
# laag na te lopen: op diepte 1 is het verschil vast óf de verhouding vast.
fout = []
for n in range(200):
    t = wereld.maak("puzzel", 1, n)
    if t is None:
        continue
    rij = [int(x) for x in re.findall(r"-?\d+", t.opgave)] + [int(t.oplossing)]
    verschillen = {rij[i + 1] - rij[i] for i in range(len(rij) - 1)}
    verhoudingen = {rij[i + 1] / rij[i] for i in range(len(rij) - 1) if rij[i]}
    if len(verschillen) != 1 and len(verhoudingen) != 1:
        fout.append(t.opgave)
toets("de eenvoudigste rijen hebben een vast verschil of een vaste verhouding",
      not fout,
      "voor de samengestelde rijen bestaat geen onafhankelijke bron; die "
      "worden hieronder op hun gedrág getoetst")

print()

# --- 2. Maakt diepte het werkelijk moeilijker? -----------------------------
# Een oplosser die alleen de eenvoudigste regel kent, hoort het ondiep goed te
# doen en diep te verdrinken. Doet hij het overal even goed, dan is diepte
# alleen een ander uiterlijk.

print("--- Maakt diepte het moeilijker? ---")


def domme_oplosser(taak):
    """Kent één regel: tel het laatste verschil er nog eens bij op."""
    rij = [int(x) for x in re.findall(r"-?\d+", taak.opgave)]
    if len(rij) < 2:
        return None
    return rij[-1] + (rij[-1] - rij[-2])


scores = []
for diepte in (1, 2, 3, 4, 5):
    proef = [t for t in (wereld.maak("puzzel", diepte, n) for n in range(300)) if t][:200]
    goed = sum(1 for t in proef if t.nakijk(domme_oplosser(t)))
    scores.append(goed / len(proef))
    print(f"         diepte {diepte:>2}: domme oplosser haalt {goed / 2:>5.0f}%")
toets("de domme regel werkt ondiep en verdrinkt dieper",
      scores[0] > 0.3 and max(scores[2:]) < 0.15,
      "diepte vraagt dus werkelijk iets anders en is niet alleen een ander "
      "uiterlijk — dit was de fout in de eerste opzet")

lengtes = [sum(len(wereld.maak("rekenen", d, n).opgave) for n in range(50)) / 50
           for d in (1, 4, 8, 12)]
toets("de uitdrukkingen worden langer met de diepte",
      lengtes == sorted(lengtes),
      "gemiddeld " + ", ".join(f"{x:.0f}" for x in lengtes) + " tekens")


# Elke stap in een uitwerking moet een ware bewerking zijn, en de laatste moet
# het antwoord opleveren. De eerste opzet plakte het antwoord er los achter:
#   ... ; 797 - 397 = 400 ; 797 + 800 = 1597
# Die 800 kwam nergens vandaan. Ze leerde dus een methode die niet uitkomt.
import re as _re                                                    # noqa: E402


def _stappen_kloppen(taak):
    for stap in taak.uitwerking.split(" ; "):
        gevonden = _re.fullmatch(r"(-?\d+) ([-+*:]) (-?\d+) = (-?\d+)", stap.strip())
        if not gevonden:
            continue                    # beschrijvende regel, geen bewerking
        a, op, b, uit = int(gevonden[1]), gevonden[2], int(gevonden[3]), int(gevonden[4])
        echt = (a + b if op == "+" else a - b if op == "-"
                else a * b if op == "*" else (a // b if b else None))
        if echt != uit:
            return False
    return True


for familie in wereld.FAMILIES:
    stuk = [t for t in (wereld.maak(familie, d, n)
                        for d in range(1, 6) for n in range(120)) if t]
    fout = [t for t in stuk if not _stappen_kloppen(t)]
    komt_uit = [t for t in stuk if not t.nakijk(t.uitwerking)]
    toets(f"elke stap in een {familie}-uitwerking is een ware bewerking",
          not fout, f"{len(stuk)} uitwerkingen nagerekend")
    toets(f"en de {familie}-uitwerking komt uit op het antwoord",
          not komt_uit,
          "de eerste opzet plakte bij puzzels het antwoord er los achter — "
          "de methode kwam er niet uit" if familie == "puzzel" else "")

print()

# --- 3. Blijft het hanteerbaar? -------------------------------------------

print("--- Blijft het hanteerbaar? ---")
langste_antwoord = 0
for familie in wereld.FAMILIES:
    for diepte in range(1, 13):
        for n in range(100):
            taak = wereld.maak(familie, diepte, n)
            if taak:
                langste_antwoord = max(langste_antwoord, len(taak.oplossing))
toets("de antwoorden blijven kort genoeg om zinvol te zijn",
      langste_antwoord <= 16,
      f"langste antwoord {langste_antwoord} tekens — bij de eerste opzet waren "
      f"dat er zestien op diepte 8, en dan meet je overtypen")

ontaard = [t.opgave for d in range(1, 13) for n in range(100)
           if (t := wereld.maak("code", d, n))]
toets("er staan geen zinloze stukken in de programma's",
      not any(re.search(r"\((\w+) [-] \1\)", p) for p in ontaard),
      "geen (a - a) en geen (14 - 14): dat maakt een opgave langer zonder hem "
      "moeilijker te maken")

reeks = wereld.leerreeks("code", 11, 40)
toets("wat niet in het venster past wordt overgeslagen",
      all(wereld.past(t) for t in reeks) and len(reeks) == 40,
      f"op diepte 11 past lang niet alles; leerreeks zoekt door tot er "
      f"{len(reeks)} bruikbare zijn")

print()

# --- 4. Raakt de wereld op? ------------------------------------------------

print("--- Raakt de wereld op? ---")
for familie in wereld.FAMILIES:
    regel = []
    for diepte in (1, 3, 6, 12):
        uniek = len({t.opgave for n in range(2000) if (t := wereld.maak(familie, diepte, n))})
        regel.append(f"d{diepte}:{uniek:>5}")
    print(f"         {familie:8} " + "  ".join(regel))
toets(
    "vanaf diepte 3 geeft vrijwel elk nummer een andere opgave",
    all(len({t.opgave for n in range(2000) if (t := wereld.maak(f, 3, n))}) > 1500
        for f in wereld.FAMILIES),
    "de ruimte groeit machtsgewijs met de diepte in plaats van lineair met wat "
    "er getypt wordt",
)

print()

# --- 5. Reproduceerbaar ----------------------------------------------------

print("--- Reproduceerbaar ---")
toets("dezelfde drie argumenten geven dezelfde taak",
      wereld.maak("rekenen", 7, 123) == wereld.maak("rekenen", 7, 123))
toets("de wereld staat los van taken.py",
      wereld.maak("rekenen", 3, 5000).opgave
      != taken.maak("rekenen", 3, 5000).opgave,
      "eigen zaad, dus de wereld en de proefwerken zijn twee gescheiden dingen")

print()

# --- 6. De proefwerken -----------------------------------------------------

print("--- De proefwerken ---")
alle = proefwerken.alle()
nodig = {"grondslag", "gemengd", "diepte", "diepte2", "ladder"}
toets(
    "geen enkel proefwerk is verdwenen",
    nodig <= set(alle),
    ", ".join(f"{n} ({len(p)})" for n, p in sorted(alle.items()))
    + " — méér mag, minder nooit: een proefwerk verdwijnt niet, ook niet als "
      "het achterhaald is",
)

# diepte is gemunt vóór de schrijfwijzecorrectie en staat er nog. Dat hoort:
# een proefwerk verdwijnt nooit, ook niet als het achterhaald is.
def _per_familie(proefwerknaam, familie):
    return {o["opgave"] for o in alle[proefwerknaam].opgaven
            if o["familie"] == familie}


toets(
    "het achterhaalde proefwerk staat er nog, naast zijn opvolger",
    not (_per_familie("diepte", "rekenen") & _per_familie("diepte2", "rekenen"))
    and not (_per_familie("diepte", "code") & _per_familie("diepte2", "code")),
    "bij rekenen en code deelt diepte geen enkele opgave met diepte2 — daar is "
    "de schrijfwijze veranderd, en precies daarom was diepte onbereikbaar "
    "geworden",
)
toets(
    "en waar de schrijfwijze niet veranderde, zijn ze wél gelijk",
    _per_familie("diepte", "puzzel") == _per_familie("diepte2", "puzzel"),
    "de rijtjes schrijven onveranderd, dus die opgaven zijn identiek — dat "
    "laat zien dat het verschil werkelijk in de schrijfwijze zat en niet in "
    "iets anders",
)

try:
    proefwerken.vastleggen("grondslag", "x", [])
    geweigerd = False
except FileExistsError:
    geweigerd = True
toets("een bestaand proefwerk wordt niet overschreven", geweigerd,
      "een proefwerk dat stilletjes overschreven kan worden is geen meetlat")

gemengd = alle["gemengd"].als_taken()
soorten = {(t.familie, t.graad) for t in gemengd}
toets("op het gemengde proefwerk staan alle soorten door elkaar",
      len(soorten) == len(taken.FAMILIES) * len(taken.GRADEN),
      f"{len(soorten)} verschillende soorten op één blad — dit ontbrak, en het "
      f"toetst ook of ze ziet wélke soort ze voor zich heeft")
opeenvolgend = sum(1 for a, b in zip(gemengd, gemengd[1:])
                   if a.familie == b.familie)
toets("en ze staan werkelijk door elkaar, niet gegroepeerd",
      opeenvolgend < len(gemengd) * 0.5,
      f"{opeenvolgend} van de {len(gemengd) - 1} keer volgt dezelfde familie "
      f"op zichzelf; bij gegroepeerd zou dat bijna altijd zijn")

diep = alle["diepte"].als_taken()
toets("het diepteproefwerk toetst stof die in taken.py niet bestaat",
      {t.graad for t in diep} == {3, 6, 9}
      and max(t.graad for t in diep) > max(taken.GRADEN),
      f"dieptes {sorted({t.graad for t in diep})}, terwijl taken.py bij graad "
      f"{max(taken.GRADEN)} ophoudt")

print()

# --- 7. Het slot -----------------------------------------------------------

print("--- Het slot ---")
slot = proefwerken.stof()
toets("het slot bevat de opgaven van alle drie de proefwerken",
      len(slot) > 1500,
      f"{len(slot)} verschillende opgaven die nooit geleerd mogen worden")

for proefwerk in alle.values():
    ontbreekt = [o["opgave"] for o in proefwerk.opgaven if o["opgave"] not in slot]
    if ontbreekt:
        break
toets("er ontbreekt geen enkele opgave in het slot", not ontbreekt)

# En de proef op de som: leerstof mag nergens een proefwerkopgave opleveren.
besmet = []
for familie in wereld.FAMILIES:
    for diepte in (3, 6, 9):
        if diepte > wereld.meeste_diepte(familie):
            continue          # daar bestaat geen bruikbare stof meer
        for t in wereld.leerreeks(familie, diepte, 200, uitsluiten=slot):
            if t.opgave in slot:
                besmet.append(t.opgave)
toets("leerstof levert nooit een proefwerkopgave op", not besmet,
      "1800 taken nagelopen tegen alle drie de proefwerken")

# Tegenproef: zonder het slot zou het wél kunnen botsen, anders bewijst het
# bovenstaande niets.
# Uit precies het nummerbereik waar diepte2 uit gemunt is: zonder slot moet het
# daar wél botsen, anders bewijst de toets hierboven niets.
# (Herzien 10 aug 2026: de oude tegenproef leunde op het toeval dat nummer
# 900.000 dezelfde teksten gaf als het gemunte proefwerk; elke groei van de
# wereld brak dat. Nu wordt de botsing zelf klaargelegd.)
bekend = wereld.maak("rekenen", 3, 700_000)
met_grendel = wereld.leerreeks("rekenen", 3, 40, vanaf=700_000,
                               uitsluiten={bekend.opgave})
zonder_grendel = wereld.leerreeks("rekenen", 3, 40, vanaf=700_000)
toets("zonder het slot zou het wél misgaan",
      bekend.opgave in {t.opgave for t in zonder_grendel}
      and bekend.opgave not in {t.opgave for t in met_grendel},
      "dezelfde stroom, mét grendel mist precies de klaargelegde opgave")
toets("en het slot zelf is goed gevuld", len(slot) >= 1700,
      f"{len(slot)} proefwerkopgaven achter de grendel")

# --- de taal van de grondslag: eindes en lengtes (10 aug 2026) -------------

eindes = {"alsdan": 0, "reken_negatief": 0, "gewoon": 0}
for n in range(2000, 2600):
    t = wereld.maak("code", 3, n)
    if t is None:
        continue
    if "if " in t.opgave:
        eindes["alsdan"] += 1
    elif int(t.oplossing) < 0:
        eindes["reken_negatief"] += 1
    else:
        eindes["gewoon"] += 1
    if not t.nakijk(t.uitwerking):
        eindes = None
        break
toets("code kent if/else, en de uitwerking komt op het antwoord uit",
      eindes is not None and eindes["alsdan"] > 50,
      "stof die niet in de wereld voorkomt kan ze alleen maar verleren")
toets("code kent negatieve uitkomsten, en nakijk aanvaardt ze",
      eindes is not None and eindes["reken_negatief"] > 20)

lengtes = set()
for n in range(2000, 2400):
    t = wereld.maak("puzzel", 2, n)
    if t is not None:
        lengtes.add(t.opgave.count(","))
toets("puzzelrijen wisselen in lengte (5, 6 en 7 getoond)",
      lengtes == {5, 6, 7},
      "met altijd zes leert ze het ritme in plaats van het stopmoment")

# De drie proefwerkvormen van code (lus, lijst, def) bestaan en passen in
# hun schrijfruimte — de bug van 10 aug (uitwerking groter dan de ruimte)
# mag niet terugkomen.
from leren import ruimte_voor as _rv
vormen_gezien = set()
vormen_passen = True
for d in (3, 4, 5, 6, 8):
    for n in range(3000, 3500):
        t = wereld.maak("code", d, n)
        if t is None:
            continue
        if "def f" in t.opgave:
            soort = "def"
        elif "getallen" in t.opgave:
            soort = "lijst"
        elif "totaal" in t.opgave and "range" in t.opgave:
            soort = "lus"
        else:
            continue
        vormen_gezien.add(soort)
        if not t.nakijk(t.uitwerking) or len(t.uitwerking) > _rv(d, "code"):
            vormen_passen = False
toets("de drie proefwerkvormen van code bestaan in de wereld",
      vormen_gezien == {"lus", "lijst", "def"})
toets("en elke uitwerking past in zijn schrijfruimte", vormen_passen)

print()
print("=" * 70)
print(f"geslaagd: {geslaagd}    gefaald: {gefaald}")
print("=" * 70)
sys.exit(0 if gefaald == 0 else 1)
