"""Het gesprek — de lus die oren, brein en mond aan elkaar knoopt (O, fase 2).

Cley spreekt in op /gesprek (of typt daar); whisper maakt er tekst van
(luisteraar.py); deze regisseur legt die tekst als vraag in de
vraag-wachtrij; de kijker laat haar met haar echte brein van dit moment
antwoorden; het antwoord gaat de zeg-wachtrij in en de mond spreekt het
uit met haar v22-stem. De pagina /gesprek toont de beurten en speelt
haar stem af.

Antwoorden is geen leren: niets in deze lus verandert haar. Leren gaat
alleen via "leer haar dit" (de brievenbus, bezorgd op een rungrens). Wat
ze hoort ging al via de luisteraar de brievenbus in — hier niet anders.

Draait als daemon-thread in server.py onder systeem-python: alleen
standaardbibliotheek. Los proefdraaien kan: python3 gesprek.py
"""
import json
import os
import re
import time

MAP = "/home/arch/amber-werk/brein"
GEHOORD = "/home/arch/rapport/gehoord.json"    # wat de oren verstonden
INBOX = f"{MAP}/gesprek-inbox"                 # getypte beurten (server)
VERWERKT = f"{MAP}/gesprek-verwerkt.json"
STAND = f"{MAP}/gesprek.json"                  # de beurten, voor de pagina
VRAGEN = f"{MAP}/vraag-wachtrij"               # de kijker leest hier
ANTWOORD = f"{MAP}/vraag-antwoord.json"        # en antwoordt hier
ZEG = "/home/arch/spraak/zeg-wachtrij/gesprek.txt"
GESPROKEN = "/home/arch/rapport/gesprek.json"  # de mond meldt zich hier

# een x tussen cijfers bedoelt vermenigvuldigen — zij kent de letter x
# alleen uit lijstfilters (zelfde herschrijving als de vraag-tab)
X_ALS_KEER = re.compile(r"(?<=[\d\s])[xX](?=[\d\s])")

beurten = []
status = "rust"


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


def _toon(nieuwe_status=None):
    global status
    if nieuwe_status is not None:
        status = nieuwe_status
    _schrijf(STAND, {"beurten": beurten[-60:], "status": status,
                     "status_tijd": time.time()})


def _spreekbaar(t):
    """Symbolen worden woorden vóór de mond ze krijgt — ' * ' spreekt
    Chatterbox niet uit, 'keer' wel. Elke stap van een uitwerking wordt
    een eigen zin, zodat de mond er een pauze tussen laat. De getallen
    zelf maakt de mond al tot woorden (getallen.py)."""
    t = t.replace(" ; ", ". ").replace(";", ". ")
    t = t.replace(" * ", " keer ").replace(" + ", " plus ")
    t = t.replace(" - ", " min ").replace(" = ", " is ")
    t = t.replace("/", " gedeeld door ")
    return t


def _antwoord_van_haar(vraag, gesteld_om):
    """Wacht tot de kijker déze vraag beantwoord heeft, of geef op.
    Matchen op de vraagtekst: de kijker beantwoordt ook vraag-tab-vragen
    en het laatste antwoord wint in vraag-antwoord.json."""
    tot = time.time() + 90
    while time.time() < tot:
        a = _lees(ANTWOORD, {})
        if (a.get("tijd") or 0) > gesteld_om and a.get("vraag") == vraag:
            return a
        time.sleep(1.0)
    return None


def _mond_klaar(gelegd_om):
    tot = time.time() + 180
    while time.time() < tot:
        m = _lees(GESPROKEN, {})
        if (m.get("tijd") or 0) > gelegd_om:
            return m.get("tijd")
        time.sleep(1.0)
    return None


def _beurt_van_cley(tekst, bron):
    beurten.append({"wie": "cley", "tekst": tekst, "bron": bron,
                    "tijd": time.time()})
    _toon("denkt")
    vraag = X_ALS_KEER.sub("*", tekst).strip()[:200]
    gesteld_om = time.time()
    os.makedirs(VRAGEN, exist_ok=True)
    with open(f"{VRAGEN}/{gesteld_om:.2f}-gesprek.txt", "w") as f:
        f.write(vraag)
    a = _antwoord_van_haar(vraag, gesteld_om)
    if a is None:
        beurten.append({"wie": "amber", "tijd": time.time(),
                        "tekst": "(geen antwoord gekregen — kijkt de "
                                 "kijker wel mee?)"})
        _toon("rust")
        return
    antwoord = (a.get("antwoord") or "").strip()
    beurt = {"wie": "amber", "tekst": antwoord or "(ze schreef niets)",
             "herinnert": a.get("herinnert") or [], "tijd": time.time()}
    beurten.append(beurt)
    if not antwoord:
        _toon("rust")
        return
    _toon("spreekt")
    gelegd_om = time.time()
    # het .deel-bestand staat búiten de wachtrijmap: de mond pakt elk
    # bestand dat hij daar ziet, ook een half geschreven
    tmp = "/home/arch/spraak/gesprek.txt.deel"
    with open(tmp, "w") as f:
        f.write(_spreekbaar(antwoord))
    os.replace(tmp, ZEG)
    wav = _mond_klaar(gelegd_om)
    if wav:
        beurt["wav_tijd"] = wav
    _toon("rust")


def lus():
    global beurten
    os.makedirs(INBOX, exist_ok=True)
    beurten = (_lees(STAND, {}).get("beurten") or [])[-60:]
    verwerkt = set(_lees(VERWERKT, []))
    # wat er bij de start al ligt is oud nieuws: een herstart mag geen
    # gesprek van gisteren opnieuw gaan voeren
    for regel in _lees(GEHOORD, {}).get("gehoord") or []:
        naam = regel.get("bestand") or ""
        if naam.startswith("gesprek-"):
            verwerkt.add(naam)
    for naam in list(os.listdir(INBOX)):
        os.remove(os.path.join(INBOX, naam))
    _schrijf(VERWERKT, sorted(verwerkt))
    _toon("rust")
    print("gesprek wakker", flush=True)

    while True:
        try:
            nieuw = []
            for naam in sorted(os.listdir(INBOX)):
                if not naam.endswith(".txt"):
                    continue
                pad = os.path.join(INBOX, naam)
                try:
                    tekst = open(pad).read().strip()
                finally:
                    os.remove(pad)
                if tekst:
                    nieuw.append((tekst, "getypt"))
            gewijzigd = False
            for regel in _lees(GEHOORD, {}).get("gehoord") or []:
                naam = regel.get("bestand") or ""
                if not naam.startswith("gesprek-") or naam in verwerkt:
                    continue
                verwerkt.add(naam)
                gewijzigd = True
                tekst = (regel.get("tekst") or "").strip()
                if tekst and tekst != "(niets verstaan)":
                    nieuw.append((tekst, "spraak"))
                else:
                    beurten.append({"wie": "cley", "bron": "spraak",
                                    "tekst": "(niets verstaan)",
                                    "tijd": time.time()})
                    _toon()
            if gewijzigd:
                # meteen vastleggen, vóór het beantwoorden: een herstart
                # halverwege mag dezelfde opname niet nóg eens beantwoorden
                if len(verwerkt) > 400:
                    verwerkt = set(sorted(verwerkt)[-400:])
                _schrijf(VERWERKT, sorted(verwerkt))
            for tekst, bron in nieuw:
                _beurt_van_cley(tekst, bron)
        except Exception as e:
            print("gesprek-hapering:", e, flush=True)
            time.sleep(5)
        time.sleep(1.5)


if __name__ == "__main__":
    lus()
