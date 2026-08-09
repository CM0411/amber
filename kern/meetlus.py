"""
De meetlus — meten of ze leert, en of ze vergeet.

C is het onderdeel waar dit project om bestaat: doorleren zonder het oude te
verliezen. Deze module levert het getal waarmee dat wordt vastgesteld.

WAT HET METEN INHOUDT
---------------------
Leer familie A, meet. Leer daarna familie B, meet opnieuw. Wat A daarbij
inlevert is het vergeten. Drie getallen per familie en graad:

    winst      = score na het leren van A  −  score aan het begin
    verlies    = score na het leren van A  −  score na het leren van B
    behouden   = 1 − verlies / winst

`behouden` is het getal dat telt. 1,0 betekent dat er niets van A verloren
ging; 0,0 dat het volledig weg is. Zonder winst is behouden zinloos en wordt
het niet gerapporteerd — je kunt niet vergeten wat je nooit geleerd hebt.

WAT DE LEERDER MOET KUNNEN
--------------------------
Bewust minimaal, zodat hier alles in past — van een opzoektabel tot de
uiteindelijke leerkern:

    antwoord(taak) -> str      geef een antwoord. Leert niets.
    leer(taken)                leer van een reeks taken mét hun oplossing

Meer is er niet nodig. De meetlus weet niet en hoeft niet te weten hoe er
geleerd wordt.

DRIE REGELS DIE HIER GELDEN
---------------------------
1. **Meten gebeurt uitsluitend op de testverzameling**, nooit op leertaken.
   `taken.py` schermt die nummers af, dus besmetting loopt hier stuk in plaats
   van stilzwijgend door te gaan.
2. **Meten leert niet.** `antwoord()` mag de leerder niet veranderen. Dat is
   niet af te dwingen vanaf hier, maar het staat wel in de toets.
3. **Metingen gaan het logboek in.** Het zijn uitkomsten die je niet opnieuw
   wilt hoeven verdienen — precies wat daar volgens N in hoort.
"""

import taken


def meet(leerder, familie, graad, aantal=100):
    """De score op de meetlat. Een getal tussen 0 en 1.

    Kan de leerder een hele partij tegelijk aan, dan wordt dat gebruikt: honderd
    taken los afgaan is honderd keer door het netwerk en samen één keer. Dat is
    het verschil tussen meten dat kan wanneer je wilt en meten dat je gaat
    vermijden — en "meten is niet optioneel".
    """
    proef = taken.testverzameling(familie, graad, aantal)
    if hasattr(leerder, "antwoorden"):
        gegeven = leerder.antwoorden(proef)
    else:
        gegeven = [leerder.antwoord(t) for t in proef]
    goed = sum(1 for t, a in zip(proef, gegeven) if t.nakijk(a))
    return goed / len(proef)


def meet_alles(leerder, families=None, graden=None, aantal=100):
    """De score op elke combinatie van familie en graad."""
    families = families or taken.FAMILIES
    graden = graden or taken.GRADEN
    return {(f, g): meet(leerder, f, g, aantal)
            for f in families for g in graden}


def _sleutel(f, g):
    return f"{f}/{g}"


def c_meting(leerder, plan, aantal_leren=200, aantal_meten=100, log=None):
    """Voer een leerplan uit en meet na elke stap wat er van het oude over is.

    `plan` is een lijst van (familie, graad) in de volgorde waarin geleerd
    wordt. Na elke stap wordt álles opnieuw gemeten, niet alleen wat er net
    geleerd is — want de vraag is juist wat er met de rest gebeurt.
    """
    metingen = [{"fase": "begin", "scores": meet_alles(leerder, aantal=aantal_meten)}]
    if log:
        log.schrijf("meting", fase="begin",
                    scores={_sleutel(*k): v for k, v in metingen[0]["scores"].items()})

    for familie, graad in plan:
        leerstof = taken.leerreeks(familie, graad, aantal_leren)
        leerder.leer(leerstof)
        fase = f"na {familie}/{graad}"
        scores = meet_alles(leerder, aantal=aantal_meten)
        metingen.append({"fase": fase, "scores": scores})
        if log:
            log.schrijf("meting", fase=fase,
                        scores={_sleutel(*k): v for k, v in scores.items()})

    return {
        "plan": [list(p) for p in plan],
        "metingen": metingen,
        "vergeten": _vergeten(metingen, plan),
    }


def _vergeten(metingen, plan):
    """Wat is er verloren gegaan van wat eerder geleerd is?

    Voor elke stap in het plan: hoeveel die stap opleverde, en hoeveel daarvan
    aan het eind nog over was.
    """
    begin = metingen[0]["scores"]
    eind = metingen[-1]["scores"]
    uitkomst = []

    for i, (familie, graad) in enumerate(plan):
        sleutel = (familie, graad)
        na_deze_stap = metingen[i + 1]["scores"][sleutel]
        winst = na_deze_stap - begin[sleutel]
        verlies = na_deze_stap - eind[sleutel]

        regel = {
            "familie": familie,
            "graad": graad,
            "begin": begin[sleutel],
            "na_leren": na_deze_stap,
            "aan_het_eind": eind[sleutel],
            "winst": winst,
            "verlies": verlies,
        }
        # Zonder winst is behouden zinloos: je kunt niet vergeten wat je nooit
        # geleerd hebt. Dan liever niets rapporteren dan een getal dat nergens
        # op slaat.
        regel["behouden"] = (1 - verlies / winst) if winst > 1e-9 else None
        uitkomst.append(regel)

    return uitkomst


def tabel(uitkomst):
    """De uitkomst als leesbare tabel."""
    regels = [
        "| familie | graad | begin | na leren | aan het eind | behouden |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in uitkomst["vergeten"]:
        behouden = "—" if r["behouden"] is None else f"{r['behouden']:.0%}"
        regels.append(
            f"| {r['familie']} | {r['graad']} | {r['begin']:.0%} | "
            f"{r['na_leren']:.0%} | {r['aan_het_eind']:.0%} | {behouden} |"
        )
    return "\n".join(regels)
