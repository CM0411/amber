"""
Proefwerken — bevroren, meervoudig, uitbreidbaar.

Cley, 8 aug 2026: *"in de menselijke wereld heb je meerdere proefwerken, wat
verschil qua stof die erin staat."* Dat was raak. De meetlat toetste elke
familie apart — honderd rekensommen, dan honderd rijtjes — en zo werkt geen
enkel echt proefwerk. Op een blad staat van alles door elkaar, en dan moet je
ook nog zien wélke soort je voor je hebt. Dat was helemaal niet gemeten.

DRIE REGELS
-----------
**Een proefwerk bewaart de opgaven zelf, niet een recept.** Zou hier
`wereld.maak(...)` staan, dan verandert het proefwerk mee zodra de grammatica
ooit wordt bijgesteld — en dan zijn de cijfers van vorig jaar niet meer met die
van vandaag te vergelijken. De wereld mag groeien, een proefwerk nooit.

**Er mogen proefwerken bij komen, er verdwijnt er nooit een.** Groeit haar
wereld, dan komt er een nieuw proefwerk voor de nieuwe stof. De oude blijven
onaangeroerd staan zodat je terug kunt kijken over de hele looptijd.

**Op geen enkel proefwerk mag geoefend worden.** `stof()` levert alle
opgaveteksten van alle proefwerken; wie leerstof maakt sluit die uit. Dat is
dezelfde grendel die op 8 aug 2026 bij `taken.py` 789 besmette opgaven op 3000
ving — een kwart, en niemand had het gezien.
"""

import json
import os

MAP = "/home/arch/amber-werk/proefwerken"


class Proefwerk:
    def __init__(self, naam, beschrijving, opgaven):
        self.naam = naam
        self.beschrijving = beschrijving
        self.opgaven = opgaven          # lijst van {opgave, oplossing, familie, graad}

    def __len__(self):
        return len(self.opgaven)

    def als_taken(self):
        """De opgaven als taken, zodat de meetlus ermee overweg kan."""
        from taken import Taak
        return [Taak(familie=o["familie"], graad=o["graad"], nummer=-1,
                     opgave=o["opgave"], oplossing=o["oplossing"])
                for o in self.opgaven]


def _pad(naam):
    return os.path.join(MAP, f"{naam}.json")


def bestaat(naam):
    return os.path.exists(_pad(naam))


def vastleggen(naam, beschrijving, taken_):
    """Leg een nieuw proefwerk vast. Weigert een bestaand te overschrijven.

    Dat weigeren is het hele punt. Een proefwerk dat stilletjes overschreven kan
    worden is geen meetlat maar een momentopname, en dan is elke vergelijking
    over de tijd waardeloos.
    """
    os.makedirs(MAP, exist_ok=True)
    if bestaat(naam):
        raise FileExistsError(
            f"proefwerk {naam!r} bestaat al en wordt niet overschreven.\n"
            f"Een proefwerk ligt vast. Wil je andere stof toetsen, maak dan een "
            f"nieuw proefwerk met een eigen naam; de oude blijven staan."
        )
    inhoud = {
        "naam": naam,
        "beschrijving": beschrijving,
        "opgaven": [{"familie": t.familie, "graad": t.graad,
                     "opgave": t.opgave, "oplossing": t.oplossing}
                    for t in taken_],
    }
    tijdelijk = _pad(naam) + ".deel"
    with open(tijdelijk, "w") as f:
        json.dump(inhoud, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tijdelijk, _pad(naam))
    fd = os.open(MAP, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return len(taken_)


def laad(naam):
    with open(_pad(naam)) as f:
        inhoud = json.load(f)
    return Proefwerk(inhoud["naam"], inhoud["beschrijving"], inhoud["opgaven"])


def namen():
    if not os.path.isdir(MAP):
        return []
    return sorted(n[:-5] for n in os.listdir(MAP) if n.endswith(".json"))


def alle():
    return {naam: laad(naam) for naam in namen()}


_stof_geheugen = None


def stof():
    """Alle opgaveteksten van alle proefwerken. Dit is het slot.

    Wie leerstof maakt geeft dit mee als `uitsluiten`. Eenmalig opgebouwd, want
    het wordt bij elke reeks leerstof geraadpleegd.
    """
    global _stof_geheugen
    if _stof_geheugen is None:
        teksten = set()
        for proefwerk in alle().values():
            teksten.update(o["opgave"] for o in proefwerk.opgaven)
        _stof_geheugen = frozenset(teksten)
    return _stof_geheugen


def vergeet_stof():
    """Na het vastleggen van een nieuw proefwerk opnieuw inlezen."""
    global _stof_geheugen
    _stof_geheugen = None


def neem(leerder, naam=None, hoogstens=None):
    """Laat een leerder een proefwerk maken. Geeft het cijfer per proefwerk.

    Meten mag nooit leren: hier wordt alleen `antwoord` of `antwoorden`
    gebruikt, nooit `leer`.
    """
    uit = {}
    for proefwerknaam, proefwerk in alle().items():
        if naam is not None and proefwerknaam != naam:
            continue
        opgaven = proefwerk.als_taken()
        if hoogstens and len(opgaven) > hoogstens:
            # Gelijkmatig over het hele blad, niet de eerste zoveel.
            #
            # De opgaven staan op volgorde van familie en graad. De eerste 150
            # van `grondslag` zijn dus allemaal code uit dezelfde hoek, en dan
            # toets je één vakje terwijl het cijfer eruitziet als het hele
            # proefwerk. Op 8 aug 2026 stond daardoor 0% waar 17% had moeten
            # staan.
            stap = len(opgaven) / hoogstens
            opgaven = [opgaven[int(i * stap)] for i in range(hoogstens)]
        # Per familie apart, want de ruimte om uit te werken verschilt: bij
        # puzzels is een uitwerking altijd rond de 90 tekens, ook op diepte 1.
        # Alles in één keer afgaan met de rekenmaat kapte de puzzels af en gaf
        # ze nul terwijl ze het wel kon.
        from leren import ruimte_voor
        gegeven = [None] * len(opgaven)
        per_familie = {}
        for i, t in enumerate(opgaven):
            per_familie.setdefault(t.familie, []).append(i)
        for familie, wijzers in per_familie.items():
            stel = [opgaven[i] for i in wijzers]
            diepste = max(t.graad for t in stel)
            antwoorden = leerder.antwoorden(stel,
                                            hoogstens=ruimte_voor(
                                                diepste, familie,
                                                leerder.kern.venster))
            for i, a in zip(wijzers, antwoorden):
                gegeven[i] = a
        goed = sum(1 for t, a in zip(opgaven, gegeven) if t.nakijk(a))
        uit[proefwerknaam] = goed / len(opgaven)
    return uit
