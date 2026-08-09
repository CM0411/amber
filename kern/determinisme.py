"""
Determinisme — de eis waar alle latere code van Amber aan vastzit.

Het meetpunt van fase 1 is: honderd stappen, afsluiten, herstarten, en bit voor
bit hetzelfde uitkomen. Op een GPU is dat geen gratis eis. Standaard zijn
diverse CUDA-bewerkingen niet-deterministisch, je moet het expliciet afdwingen,
het kost snelheid, en sommige bewerkingen hebben dan geen toegestane variant
meer. Achteraf inbouwen kan niet: dan is er ook geen enkele meting uit die
periode die je nog kunt vertrouwen.

Deze module is daarom geen advies maar een grendel. Hij weigert te draaien als
het niet klopt, in plaats van stil door te gaan met een half werkende
instelling. Dat is de les van de geluidsijking van 8 aug 2026: nvidia-smi
accepteerde daar een ongeldige waarde met een waarschuwing en afsluitcode 0,
en er is zes minuten lang de verkeerde stand gemeten zonder dat iemand het zag.

GEBRUIK — de volgorde is dwingend:

    import determinisme            # MOET vóór torch
    determinisme.zet_vast(1234)

    for stap in range(...):
        determinisme.begin_stap(stap)
        ...

WAAROM begin_stap() bij elke stap
---------------------------------
De toestand van de toevalsgenerator wordt niet bewaard. In plaats daarvan wordt
hij bij elke stap opnieuw afgeleid uit (zaad, stapnummer). Dat is de keuze die
"toestand hardware-onafhankelijk opslaan" waarmaakt: een checkpoint bevat dan
twee getallen in plaats van een brok kaartspecifiek geheugen, en is leesbaar op
elke machine. Bij een GPU-upgrade verhuis je; je begint niet opnieuw.

Het dwingt ook discipline af. Elke bron van toeval loopt door één afleiding, en
hervatten vanaf stap N geeft per definitie dezelfde reeks als doorlopen tot N.
"""

import os
import sys

# CUBLAS_WORKSPACE_CONFIG moet gezet zijn vóórdat cuBLAS wordt geïnitialiseerd,
# en dat gebeurt bij de import van torch. Daarna heeft het geen effect meer en
# weigert torch determinisme voor matmul op de GPU.
_WERKRUIMTE = ":4096:8"
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", _WERKRUIMTE)

if "torch" in sys.modules:
    raise RuntimeError(
        "determinisme is geïmporteerd nádat torch al geladen was.\n"
        "CUBLAS_WORKSPACE_CONFIG heeft dan geen effect meer en determinisme "
        "voor matmul op de GPU is stil uitgeschakeld.\n"
        "Zet 'import determinisme' bovenaan, vóór elke import van torch."
    )

import random

import numpy as np
import torch

_MASKER64 = (1 << 64) - 1
_zaad = None


def _meng(x):
    """SplitMix64 — een vaste, draagbare menging.

    Bewust niet hash() of iets uit random: die zijn niet gegarandeerd gelijk
    tussen Python-versies of tussen machines, en dan is het checkpoint niet
    draagbaar terwijl het er wel zo uitziet.
    """
    x = (x + 0x9E3779B97F4A7C15) & _MASKER64
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASKER64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASKER64
    return (z ^ (z >> 31)) & _MASKER64


def zaad_voor_stap(stap, zaad=None):
    """Het zaad van één stap, afgeleid uit (zaad, stapnummer).

    Draagbaar en herhaalbaar: dezelfde twee getallen geven op elke machine
    hetzelfde resultaat.
    """
    grond = _zaad if zaad is None else zaad
    if grond is None:
        raise RuntimeError("zet_vast() is nog niet aangeroepen")
    # Twee keer mengen zodat opeenvolgende stapnummers ver uit elkaar liggen.
    return _meng(grond ^ _meng(stap)) >> 1   # >> 1: veilig binnen wat torch accepteert


def zet_vast(zaad):
    """Zet determinisme aan en controleer dat het er ook echt staat."""
    global _zaad
    _zaad = int(zaad)

    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    begin_stap(0)
    controleer()
    return stand()


def begin_stap(nummer):
    """Zet alle generatoren op het zaad van deze stap.

    Bij elke stap opnieuw, zodat hervatten vanaf een checkpoint dezelfde reeks
    geeft als doorlopen. Ook de globale generatoren, want bewerkingen als
    dropout gebruiken die en niet een generator die je zelf meegeeft.
    """
    s = zaad_voor_stap(nummer)
    random.seed(s)
    np.random.seed(s % (2**32))          # numpy accepteert maar 32 bits
    torch.manual_seed(s)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(s)
    return s


def generator(nummer, apparaat="cpu"):
    """Een losse generator voor deze stap, voor waar je expliciet wilt zijn.

    Het object zelf is apparaatgebonden, maar het zaad is dat niet — en alleen
    het zaad gaat het checkpoint in.
    """
    g = torch.Generator(device=apparaat)
    g.manual_seed(zaad_voor_stap(nummer))
    return g


def controleer():
    """Weiger door te gaan als determinisme niet werkelijk aanstaat.

    Terugcontroleren en niet vertrouwen op het feit dat er geen fout kwam.
    """
    klachten = []

    if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != _WERKRUIMTE:
        klachten.append(
            f"CUBLAS_WORKSPACE_CONFIG is "
            f"{os.environ.get('CUBLAS_WORKSPACE_CONFIG')!r} en niet {_WERKRUIMTE!r}"
        )
    if not torch.are_deterministic_algorithms_enabled():
        klachten.append("torch.use_deterministic_algorithms staat uit")
    if not torch.backends.cudnn.deterministic:
        klachten.append("cudnn.deterministic staat uit")
    if torch.backends.cudnn.benchmark:
        klachten.append(
            "cudnn.benchmark staat aan — die kiest per run een ander algoritme"
        )
    if _zaad is None:
        klachten.append("er is geen zaad gezet")

    if klachten:
        raise RuntimeError(
            "Determinisme staat niet goed:\n  - " + "\n  - ".join(klachten)
        )
    return True


def stand():
    """Wat er aanstaat, om onveranderd in elk checkpoint mee te schrijven.

    Alleen getallen en tekst, niets apparaatgebonden. Zo is achteraf vast te
    stellen onder welke instellingen een meting is gedaan — zonder dat wat
    hierin staat nodig is om het checkpoint te kúnnen laden.
    """
    return {
        "zaad": _zaad,
        "cublas_werkruimte": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
        "deterministische_algoritmen": torch.are_deterministic_algorithms_enabled(),
        "cudnn_deterministisch": bool(torch.backends.cudnn.deterministic),
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "afleiding": "splitmix64(zaad ^ splitmix64(stap)) >> 1",
    }
