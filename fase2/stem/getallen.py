"""Getallen worden woorden — spraakmodellen struikelen over kale cijfers.

`in_woorden(212996)` -> "tweehonderdtwaalfduizend negenhonderdzesennegentig"
`vertaal_tekst("66 procent")` -> "zesenzestig procent"
"""
import re

_EEN = ["nul", "een", "twee", "drie", "vier", "vijf", "zes", "zeven",
        "acht", "negen", "tien", "elf", "twaalf", "dertien", "veertien",
        "vijftien", "zestien", "zeventien", "achttien", "negentien"]
_TIEN = ["", "", "twintig", "dertig", "veertig", "vijftig", "zestig",
         "zeventig", "tachtig", "negentig"]


def _onder_honderd(n):
    if n < 20:
        return _EEN[n]
    t, e = divmod(n, 10)
    if e == 0:
        return _TIEN[t]
    koppel = "ën" if e in (2, 3) else "en"
    return f"{_EEN[e]}{koppel}{_TIEN[t]}"


def _onder_duizend(n):
    if n < 100:
        return _onder_honderd(n)
    h, rest = divmod(n, 100)
    kop = "honderd" if h == 1 else f"{_EEN[h]}honderd"
    return kop if rest == 0 else f"{kop}{_onder_honderd(rest)}"


def in_woorden(n):
    n = int(n)
    if n < 0:
        return "min " + in_woorden(-n)
    if n < 1000:
        return _onder_duizend(n)
    if n < 1_000_000:
        d, rest = divmod(n, 1000)
        kop = "duizend" if d == 1 else f"{_onder_duizend(d)}duizend"
        return kop if rest == 0 else f"{kop} {_onder_duizend(rest)}"
    m, rest = divmod(n, 1_000_000)
    kop = f"{_onder_duizend(m)} miljoen"
    return kop if rest == 0 else f"{kop} {in_woorden(rest)}"


def vertaal_tekst(tekst):
    """Alle kale getallen in een zin omzetten naar woorden."""
    tekst = tekst.replace(" ", "").replace("\xa0", "")
    # 212 996 en 212.996 eerst aaneenplakken
    tekst = re.sub(r"(\d)[ .](\d{3})\b", r"\1\2", tekst)
    tekst = re.sub(r"(\d)[ .](\d{3})\b", r"\1\2", tekst)
    tekst = re.sub(r"(\d+),(\d+)",
                   lambda m: f"{in_woorden(m.group(1))} komma "
                             + " ".join(in_woorden(c) for c in m.group(2)),
                   tekst)
    return re.sub(r"\d+", lambda m: in_woorden(m.group(0)), tekst)
