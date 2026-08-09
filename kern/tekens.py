"""
De tekenset — hoe een taak een reeks getallen wordt.

**Dit ligt voor altijd vast.** Verandert de tekenset later, dan wijzen alle
inbeddingen naar iets anders en is elk checkpoint waardeloos. Dezelfde soort
eis als determinisme en de flessenhals, en om dezelfde reden hier meteen goed.

WAAROM BYTES
------------
Nul tot en met 255 zijn de bytes van de tekst zelf, in UTF-8. Dat is de enige
keuze die nooit meer aangepast hoeft te worden:

  * er is niets te kiezen en dus niets dat later anders had gemoeten
  * Nederlands met accenten, en straks alles wat ze van internet haalt, past er
    vanzelf in zonder de tekenset uit te breiden
  * cijfers blijven los. Een gebruikelijke tokenizer plakt cijfergroepen aan
    elkaar, en dan wordt `47 * 13` kunstmatig moeilijk omdat "47" één brok is
  * en een geleende tokenizer zou ingaan tegen "wat leert bouwen we zelf"

Daarboven vier eigen tekens, en meer komen er niet bij zonder dat het een
besluit is:

  256 VRAAG      hier begint een opgave
  257 ANTWOORD   hier begint het antwoord — hierna telt de fout pas mee
  258 EIND       klaar
  259 VUL        opvulling, telt nergens in mee

DE FOUT TELT ALLEEN OVER HET ANTWOORD
-------------------------------------
`taak_naar_reeks` geeft een masker terug dat aangeeft welke posities meetellen.
Alleen het antwoord en het EIND-teken staan daarin aan. Anders leert ze de
vragen voorspellen in plaats van ze beantwoorden — ze wordt dan goed in het
verzinnen van sommen en niet in het uitrekenen ervan.
"""

VRAAG = 256
ANTWOORD = 257
EIND = 258
VUL = 259

OMVANG = 260          # de tekenset telt 260 verschillende tekens, voorgoed

NAMEN = {VRAAG: "<vraag>", ANTWOORD: "<antwoord>", EIND: "<eind>", VUL: "<vul>"}


def codeer(tekst):
    """Tekst naar een reeks getallen."""
    return list(tekst.encode("utf-8"))


def decodeer(codes):
    """Reeks getallen terug naar tekst. Eigen tekens worden overgeslagen."""
    bytes_ = bytes(c for c in codes if c < 256)
    return bytes_.decode("utf-8", errors="replace")


def toon(codes):
    """Leesbare weergave mét de eigen tekens erin, om mee te kijken."""
    stukken, buffer = [], []
    for c in codes:
        if c < 256:
            buffer.append(c)
        else:
            if buffer:
                stukken.append(bytes(buffer).decode("utf-8", errors="replace"))
                buffer = []
            stukken.append(NAMEN.get(c, f"<{c}>"))
    if buffer:
        stukken.append(bytes(buffer).decode("utf-8", errors="replace"))
    return "".join(stukken)


def taak_naar_reeks(taak):
    """Een taak als reeks getallen, met het masker dat zegt wat meetelt.

    Vorm:  VRAAG  opgave  ANTWOORD  oplossing  EIND

    Het masker staat alleen aan op de oplossing en op EIND. De opgave zelf
    telt niet mee in de fout: ze moet leren antwoorden, niet vragen verzinnen.
    """
    # `te_leren()` en niet `oplossing`: als er een uitwerking is, hoort ze die
    # te schrijven. Het nakijken kijkt naar het laatste getal, dus uitwerken
    # mag — en zonder die ruimte moet ze alles in één doorgang uitrekenen.
    doel = taak.te_leren()
    reeks = ([VRAAG] + codeer(taak.opgave)
             + [ANTWOORD] + codeer(doel) + [EIND])
    telt_mee = ([False] * (1 + len(codeer(taak.opgave)) + 1)
                + [True] * (len(codeer(doel)) + 1))
    return reeks, telt_mee


def vraag_naar_reeks(taak):
    """Alleen de vraag, tot en met het ANTWOORD-teken.

    Dit is wat je haar voorlegt als je wilt weten wat ze ervan maakt: vanaf
    hier moet ze zelf verder.
    """
    return [VRAAG] + codeer(taak.opgave) + [ANTWOORD]


def antwoord_uit_reeks(codes):
    """Haal het antwoord uit wat ze geschreven heeft.

    Alles tussen ANTWOORD en EIND. Ontbreekt een van beide, dan is het geen
    antwoord en komt er niets terug — liever leeg dan half.
    """
    try:
        begin = codes.index(ANTWOORD) + 1
    except ValueError:
        return ""
    codes = list(codes[begin:])
    if EIND in codes:
        codes = codes[:codes.index(EIND)]
    return decodeer(codes)


def bundel(reeksen, maskers, lengte=None):
    """Zet reeksen van ongelijke lengte in één rechthoek.

    Opvulling met VUL, en het masker staat daar uit — opvulling mag nergens in
    meetellen, anders leert ze VUL voorspellen en ziet de fout er goed uit
    terwijl er niets gebeurt.
    """
    lengte = lengte or max(len(r) for r in reeksen)
    uit, uit_masker = [], []
    for reeks, masker in zip(reeksen, maskers):
        if len(reeks) > lengte:
            raise ValueError(
                f"reeks van {len(reeks)} past niet in een venster van {lengte}"
            )
        tekort = lengte - len(reeks)
        uit.append(list(reeks) + [VUL] * tekort)
        uit_masker.append(list(masker) + [False] * tekort)
    return uit, uit_masker
