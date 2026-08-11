"""
Namaakleerders — om de meetlus te kunnen toetsen vóórdat er een leerkern is.

Deze leren niets in de zin die dit project bedoelt. Ze passen een regeltje op
een reeks voorbeelden en gebruiken dat daarna. Dat is precies genoeg om vast te
stellen of de meetlus meet wat hij beweert te meten.

Twee stuks, en het verschil ertussen is de hele toets:

  * `EenRegelLeerder` onthoudt één regel. Leert hij iets nieuws, dan is het
    oude weg — een karikatuur van catastrofaal vergeten
  * `RegelPerSoortLeerder` onthoudt een regel per familie en graad, en vergeet
    dus niets

Ziet de meetlus het verschil tussen die twee niet, dan meet hij niets.

Ze doen alleen rekenen en puzzels. Codeopgaven vragen om het nabootsen van een
programma en dat kan geen regeltje — die familie blijft dus op nul staan, wat
meteen toetst of de meetlus netjes omgaat met "hier is niets geleerd".
"""

import re


def _getallen(opgave):
    return [int(x) for x in re.findall(r"-?\d+", opgave)]


# --- de regels die geprobeerd worden ---------------------------------------
# Elk neemt de getallen uit de opgave en geeft een antwoord, of None als het
# niet toepasbaar is.

def _som(n):
    return sum(n)


def _verschil(n):
    return n[0] - n[1] if len(n) >= 2 else None


def _product(n):
    return n[0] * n[1] if len(n) >= 2 else None


def _product_plus(n):
    return n[0] * n[1] + n[2] if len(n) >= 3 else None


def _product_min(n):
    return n[0] * n[1] - n[2] if len(n) >= 3 else None


def _haakjes(n):
    return (n[0] + n[1]) * n[2] - n[3] if len(n) >= 4 else None


def _rij_vast(n):
    return n[-1] + (n[1] - n[0]) if len(n) >= 2 else None


def _rij_maal(n):
    if len(n) >= 2 and n[0] != 0 and n[1] % n[0] == 0:
        return n[-1] * (n[1] // n[0])
    return None


def _rij_som_twee(n):
    return n[-1] + n[-2] if len(n) >= 2 else None


def _rij_gevlochten(n):
    return n[-2] + (n[2] - n[0]) if len(n) >= 3 else None


def _rij_tweede_orde(n):
    if len(n) < 3:
        return None
    eerste = [n[i + 1] - n[i] for i in range(len(n) - 1)]
    return n[-1] + eerste[-1] + (eerste[1] - eerste[0])


REGELS = {
    "som": _som,
    "verschil": _verschil,
    "product": _product,
    "product_plus": _product_plus,
    "product_min": _product_min,
    "haakjes": _haakjes,
    "rij_vast": _rij_vast,
    "rij_maal": _rij_maal,
    "rij_som_twee": _rij_som_twee,
    "rij_gevlochten": _rij_gevlochten,
    "rij_tweede_orde": _rij_tweede_orde,
}


def _beste_regel(taken_):
    """Welke regel verklaart deze voorbeelden het best?"""
    beste, beste_score = None, 0.0
    for naam, regel in REGELS.items():
        goed = 0
        for t in taken_:
            try:
                uitkomst = regel(_getallen(t.opgave))
            except (IndexError, ZeroDivisionError):
                uitkomst = None
            if uitkomst is not None and t.nakijk(uitkomst):
                goed += 1
        score = goed / len(taken_)
        if score > beste_score:
            beste, beste_score = naam, score
    return beste, beste_score


def _pas_toe(naam, taak):
    if naam is None:
        return ""
    try:
        uitkomst = REGELS[naam](_getallen(taak.opgave))
    except (IndexError, ZeroDivisionError):
        return ""
    return "" if uitkomst is None else str(uitkomst)


class EenRegelLeerder:
    """Onthoudt één regel. Iets nieuws leren wist het oude."""

    def __init__(self):
        self.regel = None

    def leer(self, taken_):
        naam, score = _beste_regel(taken_)
        if naam is not None:
            self.regel = naam          # het oude is hierbij weg

    def antwoord(self, taak):
        return _pas_toe(self.regel, taak)


class RegelPerSoortLeerder:
    """Onthoudt een regel per familie en graad. Vergeet dus niets."""

    def __init__(self):
        self.regels = {}

    def leer(self, taken_):
        soort = (taken_[0].familie, taken_[0].graad)
        naam, score = _beste_regel(taken_)
        if naam is not None:
            self.regels[soort] = naam

    def antwoord(self, taak):
        return _pas_toe(self.regels.get((taak.familie, taak.graad)), taak)


class StampLeerder:
    """Onthoudt letterlijk de opgaven die hij gezien heeft.

    Generaliseert niet. Op de meetlat scoort hij dus nul, hoeveel hij ook
    geleerd heeft — en dat is precies de toets of de meetlat werkelijk
    afgeschermd is.
    """

    def __init__(self):
        self.tabel = {}

    def leer(self, taken_):
        for t in taken_:
            self.tabel[t.opgave] = t.oplossing

    def antwoord(self, taak):
        return self.tabel.get(taak.opgave, "")
