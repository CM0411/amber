"""
Taken — de meetopstelling van fase 1.

"Meten is niet optioneel. Elke taak krijgt vanaf dag één een familie en een
moeilijkheidsgraad. Zonder dat kun je later niet meten of ze vergeet, en dan
weet je niet of het systeem werkt."

Drie families, zoals vastgelegd: **code, rekenen, puzzel.**

VIER KEUZES DIE HIER VASTLIGGEN
-------------------------------
**1. Taken worden gemaakt, niet bewaard.** Een taak volgt volledig uit
`(familie, graad, nummer)`. Er is dus geen bestand met opgaven dat kan
verlopen, uiteenlopen tussen machines, of half meeverhuizen. Taak 400 van
familie "rekenen" graad 3 is over vijf jaar op een andere kaart dezelfde taak.

**2. Het taakzaad staat los van het leerzaad.** Zou het taakuniversum meebewegen
met het zaad van een leerrun, dan kun je twee runs niet meer vergelijken — je
weet dan niet of een verschil aan het leren lag of aan andere sommen. Daarom
een eigen, vaste constante die nooit verandert.

**3. De testverzameling is afgeschermd in code, niet met een afspraak — en op
inhoud, niet alleen op nummer.** De nummers onder TEST_TOT zijn de meetlat.
Maar afschermen op nummer alleen is niet genoeg: dezelfde opgave kan onder een
leernummer én onder een meetlatnummer opduiken. Het zijn dan andere nummers en
dezelfde som, en wie zijn leertaken uit het hoofd leert scoort punten op de
meetlat zonder iets te kunnen. Daarom wordt óók de opgavetekst vergeleken.
Gevonden op 8 aug 2026 doordat een leerder die niets anders doet dan stampen
niet op nul uitkwam. Net als bij T en U: raakt de meetlat besmet, dan is de
meting voorgoed weg, en dat laat je niet aan discipline over.

**4. Nakijken is exact.** Geen "bijna goed". Elke familie levert een antwoord
op dat letterlijk vergeleken kan worden, want een score die van een oordeel
afhangt is geen meting.

DE MOEILIJKHEIDSGRAAD
---------------------
Graad 1 tot en met 5, oplopend in het aantal en de zwaarte van de bewerkingen.

Eerlijk over wat dat níét is: **het is geen strikt geordende schaal.** Graad 3
bij rekenen is één vermenigvuldiging en graad 2 is één optelling met grotere
getallen — dat is een andere bewerking, niet aantoonbaar een zwaardere. Wie kan
vermenigvuldigen vindt graad 3 makkelijker dan graad 2.

Dat is geen probleem voor waar de graad voor dient. Bij C wil je weten of ze op
graad 2 achteruitgaat terwijl graad 4 vooruitgaat, en daarvoor moeten de graden
alleen **stabiel** zijn en **onderling te onderscheiden** — niet perfect geijkt.
Wat wél hard is: graad 4 en 5 vragen meerdere bewerkingen achter elkaar en zijn
daarmee aantoonbaar zwaarder dan 1 tot en met 3.
"""

import re
from dataclasses import dataclass

FAMILIES = ("code", "rekenen", "puzzel")
GRADEN = (1, 2, 3, 4, 5)

# Nummers 0 t/m 199 zijn de meetlat en worden nooit geleerd.
#
# Bewust niet ruimer. De meetlat wordt óók op inhoud afgeschermd, en elke
# opgave die de meetlat bezet is er één die niet meer geleerd kan worden. Bij
# de krapste families — rekenen graad 1 is enkelvoudige cijfers en heeft er van
# nature maar ruim duizend — zou een meetlat van duizend het grootste deel van
# de leerstof opeten.
TEST_TOT = 200

# Vast, en verandert nooit. Zie keuze 2 hierboven.
TAAK_ZAAD = 0x416D626572          # "Amber"

_MASKER64 = (1 << 64) - 1


def _meng(x):
    """SplitMix64 — dezelfde menging als in determinisme.py.

    Bewust niet hash() of random: die zijn niet gegarandeerd gelijk tussen
    Python-versies of machines, en dan verandert het taakuniversum stilzwijgend
    onder je metingen door.
    """
    x = (x + 0x9E3779B97F4A7C15) & _MASKER64
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASKER64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASKER64
    return (z ^ (z >> 31)) & _MASKER64


class Trekker:
    """Een piepklein toevalsgeneratortje op SplitMix64.

    Eigen implementatie en niet random.Random, om dezelfde reden als hierboven:
    draagbaarheid over versies en machines heen. Wat hier uitkomt moet over
    jaren nog exact hetzelfde zijn.
    """

    def __init__(self, zaad):
        self._s = zaad & _MASKER64

    def _volgende(self):
        self._s = _meng(self._s)
        return self._s

    def geheel(self, laag, hoog):
        """Een geheel getal in [laag, hoog]."""
        return laag + self._volgende() % (hoog - laag + 1)

    def keuze(self, opties):
        return opties[self._volgende() % len(opties)]


def _zaad_van(familie, graad, nummer):
    kern = _meng(TAAK_ZAAD ^ _meng(FAMILIES.index(familie) * 1_000_003))
    return _meng(kern ^ _meng(graad * 7919 + nummer))


_GETAL = re.compile(r"-?\d+")


@dataclass(frozen=True)
class Taak:
    familie: str
    graad: int
    nummer: int
    opgave: str
    oplossing: str
    uitwerking: str = None

    @property
    def is_meetlat(self):
        return self.nummer < TEST_TOT

    def te_leren(self):
        """Wat ze hoort te schrijven: de uitwerking als die er is.

        `13 * 8 * 11` in één keer uitrekenen moet in één doorgang door het
        netwerk, en daar is geen ruimte voor. Een mens schrijft `13 * 8 = 104`
        en dan `104 * 11 = 1144`. Op 8 aug 2026 bleek dat het verschil te zijn
        tussen 4% en bruikbaar: zonder tussenstappen zat ze er stelselmatig
        nét naast — ze schatte, ze rekende niet.
        """
        return self.uitwerking or self.oplossing

    def nakijk(self, antwoord):
        """Het laatste getal dat ze opschreef, tegen de oplossing.

        Ze mag dus uitwerken. Wat telt is waar ze uitkomt — het laatste getal.
        Voor taken zónder uitwerking verandert er niets: dan is dat ene getal
        meteen het antwoord, en de bevroren proefwerken blijven gewoon werken.
        """
        gevonden = _GETAL.findall(str(antwoord))
        if not gevonden:
            return False
        juist = _GETAL.findall(self.oplossing)
        return bool(juist) and gevonden[-1] == juist[-1]


# --- rekenen ---------------------------------------------------------------
# Oplopend in het aantal bewerkingen en in de grootte van de getallen.

def _rekenen(t, graad):
    if graad == 1:
        # Enkelvoudige cijfers blijven het kenmerk van deze graad, maar met
        # twee óf drie termen en met plus én min. Alleen a+b zou 81 opgaven
        # opleveren en die kent ze na een middag.
        a, b = t.geheel(1, 9), t.geheel(1, 9)
        vorm = t.keuze(("+", "-", "+3", "-3"))
        if vorm == "+":
            return f"{a} + {b}", a + b
        if vorm == "-":
            return f"{a} - {b}", a - b
        c = t.geheel(1, 9)
        if vorm == "+3":
            return f"{a} + {b} + {c}", a + b + c
        return f"{a} + {b} - {c}", a + b - c
    if graad == 2:
        a, b = t.geheel(10, 99), t.geheel(10, 99)
        if t.keuze((True, False)):
            return f"{a} + {b}", a + b
        return f"{a} - {b}", a - b
    if graad == 3:
        a, b = t.geheel(2, 99), t.geheel(2, 19)
        return f"{a} * {b}", a * b
    if graad == 4:
        a, b, c = t.geheel(2, 25), t.geheel(2, 19), t.geheel(1, 99)
        if t.keuze((True, False)):
            return f"{a} * {b} + {c}", a * b + c
        return f"{a} * {b} - {c}", a * b - c
    a, b, c, d = (t.geheel(2, 40), t.geheel(1, 40),
                  t.geheel(2, 12), t.geheel(1, 60))
    return f"({a} + {b}) * {c} - {d}", (a + b) * c - d


# --- puzzel ----------------------------------------------------------------
# Eén soort: een rij voortzetten. Oplopend van vast verschil naar een regel
# die je alleen vindt door twee stappen terug te kijken.

def _puzzel(t, graad):
    if graad == 1:
        # Ook dalende rijen, anders is "het gaat omhoog" al de halve oplossing.
        start, stap = t.geheel(1, 99), t.geheel(2, 19)
        if t.keuze((True, False)):
            stap = -stap
        rij = [start + i * stap for i in range(5)]
    elif graad == 2:
        start, factor = t.geheel(1, 150), t.geheel(2, 6)
        lengte = t.keuze((4, 5))
        rij = [start * factor**i for i in range(lengte)]
    elif graad == 3:
        # Twee rijen door elkaar gevlochten.
        a, sa = t.geheel(1, 15), t.geheel(2, 7)
        b, sb = t.geheel(20, 40), t.geheel(2, 7)
        rij = []
        for i in range(3):
            rij.append(a + i * sa)
            rij.append(b + i * sb)
        rij = rij[:6]
    elif graad == 4:
        # Het verschil groeit zelf ook: tweede orde.
        start, stap, groei = t.geheel(1, 60), t.geheel(1, 15), t.geheel(1, 9)
        rij, waarde, huidig = [], start, stap
        for _ in range(5):
            rij.append(waarde)
            waarde += huidig
            huidig += groei
    else:
        # Elk getal is de som van de twee ervoor.
        a, b = t.geheel(1, 40), t.geheel(1, 40)
        rij = [a, b]
        for _ in range(4):
            rij.append(rij[-1] + rij[-2])

    volgende = _volgende_van(rij, graad)
    getoond = ", ".join(str(x) for x in rij)
    return f"Zet voort: {getoond}, ?", volgende


def _volgende_van(rij, graad):
    if graad == 1:
        return rij[-1] + (rij[1] - rij[0])
    if graad == 2:
        return rij[-1] * (rij[1] // rij[0])
    if graad == 3:
        return rij[-2] + (rij[2] - rij[0])
    if graad == 4:
        eerste = [rij[i + 1] - rij[i] for i in range(len(rij) - 1)]
        tweede = eerste[1] - eerste[0]
        return rij[-1] + eerste[-1] + tweede
    return rij[-1] + rij[-2]


# --- code ------------------------------------------------------------------
# Eerste vorm: "wat drukt dit af?" — het programma wordt samen met zijn uitkomst
# opgebouwd, dus er hoeft niets uitgevoerd te worden om het antwoord te weten.
# Dat is exact én veilig. Zelf code láten schrijven is een latere vorm; daar is
# eerst iets voor nodig dat code kan schrijven.

def _code(t, graad):
    if graad == 1:
        a, b = t.geheel(1, 99), t.geheel(1, 99)
        if t.keuze((True, False)):
            return f"a = {a}\nb = {b}\nprint(a + b)", a + b
        return f"a = {a}\nb = {b}\nprint(a - b)", a - b
    if graad == 2:
        a, b = t.geheel(1, 99), t.geheel(1, 99)
        programma = (f"a = {a}\nb = {b}\n"
                     f"if a > b:\n    print(a - b)\nelse:\n    print(b - a)")
        return programma, abs(a - b)
    if graad == 3:
        # Ook de lus zelf varieert, niet alleen de getallen erin — anders is
        # het één vorm met een ander cijfer erin en leert ze die vorm uit haar hoofd.
        n, start = t.geheel(3, 20), t.geheel(0, 50)
        vorm = t.keuze(("i", "2i", "i2"))
        if vorm == "i":
            body, uitkomst = "totaal += i", start + sum(range(1, n + 1))
        elif vorm == "2i":
            body, uitkomst = "totaal += i * 2", start + sum(2 * i for i in range(1, n + 1))
        else:
            body, uitkomst = "totaal += i * i", start + sum(i * i for i in range(1, n + 1))
        programma = (f"totaal = {start}\nfor i in range(1, {n + 1}):\n"
                     f"    {body}\nprint(totaal)")
        return programma, uitkomst
    if graad == 4:
        getallen = [t.geheel(1, 40) for _ in range(t.geheel(4, 8))]
        drempel = t.geheel(5, 30)
        if t.keuze((True, False)):
            programma = (f"getallen = {getallen}\n"
                         f"print(len([x for x in getallen if x > {drempel}]))")
            return programma, len([x for x in getallen if x > drempel])
        programma = (f"getallen = {getallen}\n"
                     f"print(sum([x for x in getallen if x > {drempel}]))")
        return programma, sum(x for x in getallen if x > drempel)
    n, f, k = t.geheel(2, 15), t.geheel(2, 20), t.geheel(0, 9)
    programma = (f"def f(x):\n    return x * {f} + {k}\n\n"
                 f"totaal = 0\nfor i in range(1, {n + 1}):\n"
                 f"    totaal += f(i)\nprint(totaal)")
    return programma, sum(i * f + k for i in range(1, n + 1))


_MAKERS = {"rekenen": _rekenen, "puzzel": _puzzel, "code": _code}


def maak(familie, graad, nummer):
    """Maak één taak. Volledig bepaald door de drie argumenten."""
    if familie not in FAMILIES:
        raise ValueError(f"onbekende familie {familie!r}; keuze uit {FAMILIES}")
    if graad not in GRADEN:
        raise ValueError(f"graad {graad} bestaat niet; keuze uit {GRADEN}")
    if nummer < 0:
        raise ValueError("nummer moet nul of hoger zijn")

    t = Trekker(_zaad_van(familie, graad, nummer))
    opgave, oplossing = _MAKERS[familie](t, graad)
    return Taak(familie=familie, graad=graad, nummer=nummer,
                opgave=opgave, oplossing=str(oplossing))


_meetlat_teksten = {}


def _meetlat_van(familie, graad):
    """De opgaveteksten die de meetlat bezet houdt. Eenmalig opgebouwd."""
    sleutel = (familie, graad)
    if sleutel not in _meetlat_teksten:
        _meetlat_teksten[sleutel] = frozenset(
            maak(familie, graad, n).opgave for n in range(TEST_TOT)
        )
    return _meetlat_teksten[sleutel]


def is_besmet(taak):
    """Komt deze opgave ook in de meetlat voor?

    Op nummer kan een taak buiten de meetlat vallen en op tekst er toch in
    zitten — dezelfde som onder een ander nummer. Wie zulke taken leert scoort
    op de meetlat zonder iets te kunnen.
    """
    return taak.opgave in _meetlat_van(taak.familie, taak.graad)


def leertaak(familie, graad, nummer):
    """Een taak om van te leren. Weigert alles wat de meetlat raakt.

    Dit is de grendel achter keuze 3: besmetting is hiermee een fout die meteen
    stukloopt, en niet iets waar je maanden later achterkomt als de meting al
    waardeloos is. Voor een reeks gebruik je `leerreeks()` — die slaat besmette
    taken over in plaats van eroverheen te vallen.
    """
    if nummer < TEST_TOT:
        raise ValueError(
            f"nummer {nummer} hoort bij de meetlat (alles onder {TEST_TOT}) "
            f"en mag nooit geleerd worden.\n"
            f"Gebruik nummers vanaf {TEST_TOT}, of maak() als je bewust een "
            f"meetlattaak wilt bekijken."
        )
    taak = maak(familie, graad, nummer)
    if is_besmet(taak):
        raise ValueError(
            f"{familie} graad {graad} nummer {nummer} valt buiten de meetlat "
            f"qua nummer, maar de opgave staat er wél in:\n"
            f"  {taak.opgave!r}\n"
            f"Leren hiervan besmet de meting. Gebruik leerreeks(), die slaat "
            f"zulke taken over."
        )
    return taak


def testverzameling(familie, graad, aantal=100):
    """De meetlat. Altijd dezelfde taken, in dezelfde volgorde."""
    if aantal > TEST_TOT:
        raise ValueError(f"de meetlat heeft maar {TEST_TOT} taken per graad")
    return [maak(familie, graad, n) for n in range(aantal)]


def leerreeks(familie, graad, aantal, vanaf=TEST_TOT):
    """Een reeks leertaken. Besmette taken worden overgeslagen.

    Zoekt door tot er `aantal` schone taken zijn. Loopt dat te ver op, dan is
    de voorraad van deze familie en graad te krap voor wat er gevraagd wordt en
    zegt hij dat, in plaats van eindeloos door te zoeken.
    """
    gevonden = []
    nummer = vanaf
    grens = vanaf + aantal * 20 + 1000
    while len(gevonden) < aantal:
        if nummer > grens:
            raise ValueError(
                f"{familie} graad {graad}: niet genoeg schone leertaken.\n"
                f"{len(gevonden)} van de gevraagde {aantal} gevonden tussen "
                f"{vanaf} en {nummer}. De voorraad van deze graad is te klein "
                f"naast een meetlat van {TEST_TOT}."
            )
        taak = maak(familie, graad, nummer)
        if not is_besmet(taak):
            gevonden.append(taak)
        nummer += 1
    return gevonden
