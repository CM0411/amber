"""
De wereld waarin ze leeft — bouwstenen die stapelen, geen catalogus.

Uit de roadmap: *"F is de zwaarste ontwerpbeslissing van het project: te simpel
en ze is binnen een week uitgeleerd, te rijk en je meet niets meer."* En bij de
risico's staat "F blijkt na een jaar te simpel gekozen" op 40%.

`taken.py` is een catalogus: vijftien vaste soorten. Zodra ze die kan is haar
wereld op, en uitbreiden betekent dat er elk jaar iemand nieuwe soorten zit te
verzinnen. Dat schaalt niet over jaren.

Hier staan in plaats daarvan **bouwstenen die je op elkaar kunt stapelen**. Bij
rekenen zijn dat getallen, plus, min, keer en haakjes — meer niet. Maar je kunt
ze zo diep stapelen als je wilt:

    diepte 1:  47
    diepte 2:  (3 + 7)
    diepte 3:  ((3 + 7) * 4)
    diepte 5:  (((3 + 7) * 4) - ((2 * 6) + 9))

Moeilijker worden is dus dieper stapelen, en dat is een **schuif** in plaats van
vijf treden waar je op een gegeven moment vanaf valt. De ruimte groeit
machtsgewijs met de diepte in plaats van lineair met wat er getypt wordt.

TWEE DINGEN DIE HIER VASTLIGGEN
-------------------------------
**De wereld mag groeien, de proefwerken nooit.** Wat hier gemaakt wordt is
leerstof. De proefwerken staan in `proefwerken.py` en veranderen niet — anders
zijn metingen van vandaag niet te vergelijken met die van vorig jaar.

**Niets uit deze wereld mag met een proefwerk botsen.** Niet op nummer en niet
op tekst. Diezelfde grendel als bij `taken.py`, en om dezelfde reden: op 8 aug
2026 bleek een kwart van de leerstof daar dezelfde opgaven op te leveren als de
meetlat.

Samenstelbaarheid is bovendien precies de eigenschap die U later van haar
notatie vraagt. Een wereld die zelf uit samenstellingen bestaat maakt de kans
groter dat haar notatie dat ook wordt. Geen bewijs, wel de goede richting.
"""

from taken import FAMILIES, Taak, Trekker, _meng

# Eigen constante, los van die van taken.py: de wereld en de proefwerken zijn
# twee gescheiden dingen en moeten dat ook in hun getallen zijn.
WERELD_ZAAD = 0x5765_7265_6C64          # "Wereld"

MINSTE_DIEPTE = 1
# Gemeten 9 aug 2026, 400 opgaven per diepte: t/m 15 past 100% met uitwerking
# binnen MEESTE_TEKENS, op 16 nog 97%, op 17 nog 93%, op 18 zakt het naar 66%
# en vanaf 20 past niets meer. Zelfde maatstaf als bij code (hek op 85%):
# het hek staat op 17. Dieper dan dit is geen keuze maar het venster zelf —
# pas als het venster groeit (fase 2) kan het hek verder open.
MEESTE_DIEPTE = 17

# Per familie kan de grens lager liggen. Bij puzzels zijn de rijen vanaf diepte
# 6 zo diep gevlochten dat er geen methode meer uitkomt die het antwoord
# aflevert — 16% bruikbaar op 6, 4% daarboven. Een opgave waar alleen te raden
# valt hoort niet in haar wereld, en zonder deze grens stuurt de
# nieuwsgierigheid haar er wél heen en loopt het vast.
#
# Langere rijen (gemeten 10 aug 2026, zie _rij) redden de verkláring — diepte
# 6 gaat van 16% naar 36% verklaarbaar, evenveel als diepte 5 zelf — maar de
# uitwerking van zo'n diepe vlecht is 500–1200 tekens en past niet in het
# venster van 512: op diepte 6 past nog 2%, daarboven niets. Zelfde muur als
# rekenen 18+ en code 9+: overal is de grens het venster, niet haar kunnen.
# Het hek blijft dus op 5 tot het venster groeit (fase 2).
MEESTE_DIEPTE_PER = {"puzzel": 5, "code": 8}
# code tot 8: mét de volledige uitwerking is op diepte 8 nog 85% van de
# opgaven passend binnen het venster, op diepte 9 nog maar 4% en op 12 niets.
# Run 3 opende op 9 aug 2026 code tot 12 en crashte daar zes keer op
# "1 van de 64 taken gevonden" — een diepte zonder opgaven is geen wereld


def meeste_diepte(familie):
    return MEESTE_DIEPTE_PER.get(familie, MEESTE_DIEPTE)

# Haar venster is 512 tekens. Een opgave die daar met zijn uitwerking niet in
# past kan ze niet eens lezen. 400 laat ruimte voor de eigen tekens.
#
# Ruimer dan de eerste 200, omdat een uitwerking veel langer is dan een kaal
# antwoord: op diepte 12 is die al 247 tekens. Met 256 venster liep de lus
# meteen vast op de langste proefwerkopgave.
MEESTE_TEKENS = 400


def _zaad_van(familie, diepte, nummer):
    kern = _meng(WERELD_ZAAD ^ _meng(FAMILIES.index(familie) * 1_000_003))
    return _meng(kern ^ _meng(diepte * 7919 + nummer))


# --- rekenen ---------------------------------------------------------------
# Een uitdrukkingsboom. Samengestelde takken krijgen altijd haakjes: dan is er
# geen twijfel over de volgorde en hoeft niemand voorrangsregels te kennen om
# te controleren of het antwoord klopt.

# Voorrang, om te bepalen waar haakjes werkelijk nodig zijn.
_VOORRANG = {"+": 1, "-": 1, "*": 2}
_BLAD = 3


def _haakjes(tekst, eigen, nodig, rechts_van_min=False):
    """Zet er haakjes omheen, maar alleen als de voorrang dat vraagt.

    De eerste opzet zette overal haakjes — "dan hoeft niemand voorrangsregels
    te kennen". Dat leek zorgvuldig en was een fout: haar wereld schreef alles
    als `(66 - 55)` terwijl het bevroren proefwerk `8 + 2` vraagt. Ze had toen
    nog nooit een som zónder haakjes gezien, en scoorde daarop dus nul. Een
    meetlat waar ze principieel niet bij kan is geen meetlat.
    """
    if eigen < nodig or (rechts_van_min and eigen <= nodig):
        return f"({tekst})"
    return tekst


def _uitwerken(node, stappen):
    """Reken de boom uit en schrijf elke bewerking op.

    Dit is het verschil tussen schatten en rekenen. `13 * 8 * 11` in één
    doorgang door het netwerk is te veel gevraagd; `13 * 8 = 104` gevolgd door
    `104 * 11 = 1144` is twee keer iets makkelijks. Op 8 aug 2026 bleef ze
    zonder uitwerking op 4% steken en zat ze er stelselmatig nét naast.
    """
    if node[0] == "blad":
        return node[1]
    _, bewerking, links, rechts = node
    lw = _uitwerken(links, stappen)
    rw = _uitwerken(rechts, stappen)
    waarde = (lw + rw if bewerking == "+" else
              lw - rw if bewerking == "-" else lw * rw)
    stappen.append(f"{lw} {bewerking} {rw} = {waarde}")
    return waarde


def _reken_boom(bewerkingen, t, klein):
    """`bewerkingen` is het aantal bewerkingen dat er nog in mag.

    Diepte telt dus bewerkingen en niet lagen: diepte 1 is één bewerking, en
    dat is `3 + 7`. Zo heeft de wereld een echte bodem. In de eerste opzet was
    zelfs de makkelijkste taak `(66 - 55)` — twee cijfers en haakjes — en dan
    is er geen ingang voor iets dat vanaf nul begint.
    """
    if bewerkingen <= 0:
        n = t.geheel(1, klein)
        return str(n), _BLAD, ("blad", n)

    bewerking = t.keuze(("+", "-", "*"))
    voorrang = _VOORRANG[bewerking]

    if bewerking == "*":
        # Eén kant blijft altijd een klein getal. Twee diepe takken op elkaar
        # vermenigvuldigen laat de uitkomst machtsgewijs weglopen.
        lt, lv, lnode = _reken_boom(bewerkingen - 1, t, klein)
        rechts = t.geheel(2, 12)
        return (f"{_haakjes(lt, lv, voorrang)} * {rechts}",
                voorrang, ("op", "*", lnode, ("blad", rechts)))

    links_deel = t.geheel(0, bewerkingen - 1)
    rechts_deel = bewerkingen - 1 - links_deel
    lt, lv, lnode = _reken_boom(links_deel, t, klein)
    rt, rv, rnode = _reken_boom(rechts_deel, t, klein)
    return (f"{_haakjes(lt, lv, voorrang)} {bewerking} "
            f"{_haakjes(rt, rv, voorrang, rechts_van_min=(bewerking == '-'))}",
            voorrang, ("op", bewerking, lnode, rnode))


def _rekenen(diepte, t):
    # De getallen groeien geleidelijk mee met de diepte. In de eerste opzet
    # sprong het van enkele cijfers op diepte 1 naar 1–99 op diepte 2, en dan
    # veranderen er twee dingen tegelijk: een bewerking erbij én grotere
    # getallen. Haar score zakte daar van 77% naar 7%. Een schuif hoort
    # geleidelijk te zijn, anders is het alsnog een trede.
    klein = min(40, 9 * diepte)
    tekst, _, node = _reken_boom(diepte, t, klein)
    stappen = []
    waarde = _uitwerken(node, stappen)
    return tekst, waarde, " ; ".join(stappen)


# --- rijen -----------------------------------------------------------------
# Regels die uit regels bestaan. De basis is "tel er iets bij" of "vermenigvuldig
# met iets"; daarboven kun je twee regels afwisselen, of een regel op de
# verschillen loslaten in plaats van op de getallen zelf.

def _rij_reeks(diepte, t, lengte):
    """Bouw een reeks van `lengte` getallen.

    Een reeks, niet een "volgende waarde"-functie — anders kun je een regel niet
    op een andere regel loslaten. Dat was de fout in de eerste opzet: "tweede
    orde" negeerde de regel eronder, en diepte 5 gaf hetzelfde als diepte 8.
    """
    if diepte <= 1:
        soort = t.keuze(("maal", "plus", "plus", "beide-vorige"))
        if soort == "maal":
            # Tot en met ×6, zoals de grondslag vraagt — tot 11 aug 2026 was
            # dit ×2/×3 en stond puzzel graad 2 daardoor op 30%: bij een
            # ×5-rij viel ze terug op aftrekken en verdwaalde. De start
            # krimpt mee met de factor, zodat het laatste getal in de buurt
            # van het proefwerk blijft (~400.000) en niet ontploft.
            # Ondergrens 30: het plafond dient de kórte, getoonde rijen
            # (grondslag graad 2). Lange rijen — de strengen van diepte 6+ —
            # zouden anders op start 1–2 vastlopen en de variatie doden:
            # gemeten 11 aug 2026, puzzel d12 zakte van ~1900 naar 135
            # verschillende opgaven per 2000 nummers.
            factor = t.geheel(2, 6)
            plafond = max(30, min(150, 400_000 // factor ** max(1, lengte - 1)))
            start = t.geheel(1, plafond)
            return [start * factor ** i for i in range(lengte)]
        if soort == "beide-vorige":
            # Elk getal is de som van zijn twee voorgangers — de vorm van
            # grondslag puzzel 5, die tot 11 aug 2026 nergens in de wereld
            # bestond (0% op het proefwerk).
            uit = [t.geheel(1, 60), t.geheel(1, 60)]
            while len(uit) < lengte:
                uit.append(uit[-2] + uit[-1])
            return uit[:lengte]
        start = t.geheel(1, 30)
        stap = t.geheel(2, 19) * t.keuze((1, 1, -1))
        return [start + i * stap for i in range(lengte)]

    if t.keuze(("afwisselend", "opgeteld", "opgeteld")) == "afwisselend":
        # Twee reeksen door elkaar gevlochten.
        a = _rij_reeks(diepte - 1, t, (lengte + 1) // 2)
        b = _rij_reeks(diepte - 1, t, lengte // 2 + 1)
        return [a[i // 2] if i % 2 == 0 else b[i // 2] for i in range(lengte)]

    # De reeks eronder zijn de vérschillen van deze. Zo werkt stapelen echt:
    # een rij met een vast verschil wordt er eentje met een groeiend verschil,
    # en nog een laag erop laat die groei zelf weer groeien.
    verschillen = _rij_reeks(diepte - 1, t, lengte - 1)
    uit = [t.geheel(1, 30)]
    for v in verschillen:
        uit.append(uit[-1] + v)
    return uit


def _verklaar(rij, laag=0):
    """Leid het laatste getal af uit de rij ervóór, met een methode die werkt.

    Geeft (stappen, gelukt) terug. De eerste opzet toonde alleen de verschillen
    en plakte er dan het antwoord achter:

        47 - 22 = 25 ; 97 - 47 = 50 ; ... ; 797 + 800 = 1597

    Die 800 komt uit het niets — nergens in de uitwerking staat waar hij vandaan
    komt. Bij een vast verschil klopte het toevallig, daarboven niet. Ze leerde
    dus een methode die het antwoord niet oplevert, en liep vast op precies de
    plek waar het verschil begint te veranderen. Gevonden op 9 aug 2026.

    Nu wordt de methode werkelijk doorgezet: is het verschil niet vast, dan
    wordt het volgende verschil op dezelfde manier afgeleid, net zo lang tot het
    wél uitkomt.
    """
    # De laaggrens moet meegroeien met de langste rij: diepte 8 heeft zeven
    # lagen nodig. Voor rijen van zeven verandert er niets — daar stopt de
    # lengtegrens (< 3) altijd eerder dan laag 5, dus de stof tot en met
    # diepte 5 blijft bit voor bit gelijk.
    if laag > 8 or len(rij) < 3:
        return [], False

    zichtbaar, doel = rij[:-1], rij[-1]
    verschillen = [zichtbaar[i + 1] - zichtbaar[i]
                   for i in range(len(zichtbaar) - 1)]

    # 1. Vast verschil: optellen en klaar.
    if len(set(verschillen)) == 1:
        stap = verschillen[0]
        stappen = [f"{zichtbaar[i + 1]} - {zichtbaar[i]} = {stap}"
                   for i in range(len(verschillen))]
        stappen.append(f"{zichtbaar[-1]} + {stap} = {doel}")
        return stappen, zichtbaar[-1] + stap == doel

    # 2. Vaste verhouding: vermenigvuldigen.
    if all(x > 0 for x in zichtbaar):
        # **Alle** delingen moeten precies uitkomen, niet de meeste. Stond hier
        # een filter op "waar het toevallig deelbaar is", dan kwamen er stappen
        # als `47 : 22 = 2` in de uitwerking — en dan leert ze een som die niet
        # klopt. Alleen positieve getallen, want delen met een negatief getal
        # rondt de verkeerde kant op.
        delers = {zichtbaar[i + 1] // zichtbaar[i]
                  for i in range(len(zichtbaar) - 1)}
        exact = all(zichtbaar[i + 1] % zichtbaar[i] == 0
                    for i in range(len(zichtbaar) - 1))
        if exact and len(delers) == 1:
            factor = delers.pop()
            stappen = [f"{zichtbaar[i + 1]} : {zichtbaar[i]} = {factor}"
                       for i in range(len(zichtbaar) - 1)]
            stappen.append(f"{zichtbaar[-1]} * {factor} = {doel}")
            if zichtbaar[-1] * factor == doel:
                return stappen, True

    # 2b. Som van de vorige twee (grondslag puzzel 5): elk getal is de som
    #     van zijn twee voorgangers. Dit moet vóór de verschillenrecursie
    #     staan, want de verschillen van zo'n rij zijn wéér zo'n rij — daar
    #     komt de recursie nooit uit en dan bestond deze stof niet.
    if len(zichtbaar) >= 3 and all(rij[i] == rij[i - 2] + rij[i - 1]
                                   for i in range(2, len(rij))):
        stappen = [f"{rij[i - 2]} + {rij[i - 1]} = {rij[i]}"
                   for i in range(2, len(rij))]
        return stappen, True

    # 3. Het verschil verandert zelf: dezelfde methode op de verschillen.
    volgend = doel - zichtbaar[-1]
    stappen = [f"{zichtbaar[i + 1]} - {zichtbaar[i]} = {verschillen[i]}"
               for i in range(len(verschillen))]
    binnen, gelukt = _verklaar(verschillen + [volgend], laag + 1)
    if gelukt:
        stappen += binnen
        stappen.append(f"{zichtbaar[-1]} + {volgend} = {doel}")
        return stappen, True

    # 4. Twee rijen door elkaar gevlochten. Dan slaat elke andere plaats over,
    #    en zijn het in werkelijkheid twee losse rijtjes. Zonder dit valt op
    #    diepte 6 élke opgave af, want daar is bijna alles gevlochten.
    plaats = len(rij) - 1
    eigen = rij[plaats % 2::2]
    if len(eigen) >= 3:
        binnen, gelukt = _verklaar(eigen, laag + 1)
        if gelukt:
            om = ", ".join(str(x) for x in eigen[:-1])
            return [f"om en om, dus kijk naar {om}"] + binnen, True

    return [], False


def _rij(diepte, t):
    # Wisselende lengte: vijf tot zeven getallen zichtbaar. Met altijd zes
    # leert ze het rítme in plaats van het stopmoment — op het bevroren
    # proefwerk (vijf getallen) rekende ze op 10 aug 2026 alle verschillen
    # foutloos uit en sloot dan af met `45 - 45 = 0 ; 45 + 0 = 45`: één
    # verschil te veel, want haar wereld toonde er altijd zes. De methode
    # hoort bij élke lengte te werken, dus de lengte hoort te wisselen.
    getoond = t.keuze((5, 6, 7))
    # En diepere vlechten vragen langere rijen: elke "opgeteld"-laag verbruikt
    # één element en elke vlecht halveert de streng; met zeven getallen is op
    # diepte 6 zo'n 84% onverklaarbaar — te weinig bewijs op tafel om de
    # lagen af te pellen.
    lengte = getoond + 1 + 2 * max(0, diepte - 5)
    rij = _rij_reeks(max(1, diepte - 1), t, lengte)
    getoond = ", ".join(str(x) for x in rij[:-1])
    stappen, gelukt = _verklaar(rij)
    if not gelukt:
        # Geen methode die er uitkomt. Dan is dit geen eerlijke opgave: er valt
        # niets uit te werken, alleen te raden. `maak()` gooit hem weg.
        return None, None, None
    return f"Zet voort: {getoond}, ?", rij[-1], " ; ".join(stappen)


# --- code ------------------------------------------------------------------
# Een programma als reeks toewijzingen, waarbij elke regel een uitdrukking is
# over de getallen en over eerdere variabelen. Dieper betekent meer regels en
# diepere uitdrukkingen. Er wordt niets uitgevoerd om het antwoord te weten:
# de uitkomst wordt tijdens het opbouwen meegerekend.

_NAMEN = "abcdefghij"


def _code_uitdrukking(diepte, t, bekend):
    """Een uitdrukking over getallen en al bekende variabelen.

    Geeft (tekst, voorrang, waarde, node) terug. De node is dezelfde boomvorm
    als bij rekenen, zodat de uitwerking élke stap kan laten zien. De eerste
    opzet gaf per regel alleen de uitkomst — `b = 72` bij `b = a * 4 - (a + 27)`
    — en dan moet ze een berekening van drie stappen in één keer in haar hoofd
    doen. Op diepte 3 kwam ze daarmee tot 50%, op diepte 4 bleef ze plat op
    1–2% na 28.000 taken. Zelfde ziekte als bij de puzzels: een getal dat
    nergens vandaan komt. Gevonden op 9 aug 2026.
    """
    if diepte <= 1 or not bekend:
        if bekend and t.keuze((True, False)):
            naam = t.keuze(sorted(bekend))
            return naam, _BLAD, bekend[naam], ("blad", bekend[naam])
        n = t.geheel(1, 40)
        return str(n), _BLAD, n, ("blad", n)

    bewerking = t.keuze(("+", "-", "*"))
    voorrang = _VOORRANG[bewerking]

    if bewerking == "*":
        lt, lv, lw, lnode = _code_uitdrukking(diepte - 1, t, bekend)
        rechts = t.geheel(2, 9)
        return (f"{_haakjes(lt, lv, voorrang)} * {rechts}", voorrang,
                lw * rechts, ("op", "*", lnode, ("blad", rechts)))

    lt, lv, lw, lnode = _code_uitdrukking(diepte - 1, t, bekend)
    rt, rv, rw, rnode = _code_uitdrukking(diepte - 1, t, bekend)

    # Geen `a - a` en geen `14 - 14`: dat ziet er ingewikkeld uit en is nul.
    # Zulke stukken maken een opgave langer zonder hem moeilijker te maken.
    if lt == rt:
        rw = t.geheel(1, 40)
        rt, rv, rnode = str(rw), _BLAD, ("blad", rw)

    waarde = lw + rw if bewerking == "+" else lw - rw
    return (f"{_haakjes(lt, lv, voorrang)} {bewerking} "
            f"{_haakjes(rt, rv, voorrang, rechts_van_min=(bewerking == '-'))}",
            voorrang, waarde, ("op", bewerking, lnode, rnode))


def _lus_programma(diepte, t):
    """`totaal += i` en verwanten — de vorm van grondslag code graad 3.

    Het aantal rondes schaalt met de diepte én met de vorm: een kwadraat
    schrijft twee stappen per ronde en past dus minder rondes in dezelfde
    schrijfruimte. Gemeten 10 aug 2026.
    """
    # Alle drie de vormen vanaf diepte 3 — de grondslag vraagt op graad 3
    # juist `i * 2` en `i * i`, en tot 11 aug 2026 maakte de wereld die pas
    # op diepte 4, met te weinig rondes (17% op het proefwerk). De aantallen
    # passen bij venster 768; `past()` filtert wat te groot uitvalt.
    vorm = t.keuze(("i", "2i", "i2"))
    n = (t.geheel(2, 4 + 2 * diepte) if vorm == "i"
         else t.geheel(2, min(11, 3 + 2 * diepte)))
    start = t.geheel(0, 50)
    body = {"i": "totaal += i", "2i": "totaal += i * 2",
            "i2": "totaal += i * i"}[vorm]
    stappen, totaal = [], start
    for i in range(1, n + 1):
        if vorm == "i":
            erbij = i
        elif vorm == "2i":
            erbij = i * 2
            stappen.append(f"{i} * 2 = {erbij}")
        else:
            erbij = i * i
            stappen.append(f"{i} * {i} = {erbij}")
        stappen.append(f"{totaal} + {erbij} = {totaal + erbij}")
        totaal += erbij
    programma = (f"totaal = {start}\nfor i in range(1, {n + 1}):\n"
                 f"    {body}\nprint(totaal)")
    return programma, totaal, " ; ".join(stappen)


def _lijst_programma(diepte, t):
    """De lijstfilter — de vorm van grondslag code graad 4."""
    # Aantal elementen en de som-variant zijn op 10 aug 2026 tegen de
    # schrijfruimte aan gemeten: op diepte 4 alleen tellen (de som-stappen
    # pasten daar 74 tekens overheen), vanaf 5 ook optellen.
    getallen = [t.geheel(1, 40) for _ in range(t.geheel(4, min(9, 2 + diepte)))]
    drempel = t.geheel(5, 30)
    # Sinds venster 768 past de som-variant ook op diepte 4 (11 aug 2026);
    # daarvóór liepen de som-stappen daar 74 tekens over de schrijfruimte.
    tellen = True if diepte <= 3 else t.keuze((True, False))
    raak = [x for x in getallen if x > drempel]
    stappen = [f"{x} > {drempel}, telt mee" if x > drempel
               else f"{x} > {drempel} is niet zo" for x in getallen]
    if tellen:
        programma = (f"getallen = {getallen}\n"
                     f"print(len([x for x in getallen if x > {drempel}]))")
        stappen.append(f"meegeteld: {len(raak)}")
        return programma, len(raak), " ; ".join(stappen)
    programma = (f"getallen = {getallen}\n"
                 f"print(sum([x for x in getallen if x > {drempel}]))")
    som = 0
    for x in raak:
        stappen.append(f"{som} + {x} = {som + x}")
        som += x
    if not raak:
        stappen.append("niets telt mee, dus 0")
    return programma, som, " ; ".join(stappen)


def _def_programma(diepte, t):
    """`def f(x)` plus een lus — de vorm van grondslag code graad 5.

    Weinig rondes: elke ronde schrijft drie stappen. De grote aantallen van
    het proefwerk (tot vijftien rondes) passen pas als het venster groeit.
    """
    # Tot tien rondes sinds venster 768 (11 aug 2026, was zes) — het proefwerk
    # gaat tot vijftien, maar vijftien rondes × drie stappen is ~675 tekens
    # en dat past ook in 768 niet; elf schoot er op diepte 6 al 7 tekens
    # overheen. De rest is stof voor het volgende venster.
    n, f, k = t.geheel(2, min(10, 2 * diepte)), t.geheel(2, 20), t.geheel(0, 9)
    stappen, totaal = [], 0
    for i in range(1, n + 1):
        p = i * f
        stappen.append(f"f({i}): {i} * {f} = {p}")
        stappen.append(f"{p} + {k} = {p + k}")
        stappen.append(f"{totaal} + {p + k} = {totaal + p + k}")
        totaal += p + k
    programma = (f"def f(x):\n    return x * {f} + {k}\n\n"
                 f"totaal = 0\nfor i in range(1, {n + 1}):\n"
                 f"    totaal += f(i)\nprint(totaal)")
    return programma, totaal, " ; ".join(stappen)


def _code(diepte, t):
    # De taal van de grondslag, deel twee (10 aug 2026): drie programmavormen
    # die het proefwerk vraagt en die in de wereld niet bestonden — per vakje
    # gemeten bleef code graad 3–5 daardoor op exact 0%. Elke vorm vanaf de
    # diepte waar zijn uitwerking in de schrijfruimte past.
    vormen = ["regels", "regels"]
    if diepte >= 3:
        vormen.append("lus")
    if diepte >= 4:
        vormen.append("lijst")
    if diepte >= 5:
        vormen.append("def")
    vorm = t.keuze(tuple(vormen))
    if vorm == "lus":
        return _lus_programma(diepte, t)
    if vorm == "lijst":
        return _lijst_programma(diepte, t)
    if vorm == "def":
        return _def_programma(diepte, t)

    # Twee grenzen, allebei omdat een programma anders sneller groeit dan het
    # moeilijker wordt. Op diepte 12 gaf de eerste opzet regels van honderdvijftig
    # tekens — dat past niet eens in haar venster van 256, en het meet lezen in
    # plaats van begrijpen. Dieper betekent hier dus vooral méér regels, met
    # regels die zelf bescheiden blijven.
    regels_aantal = min(6, 1 + diepte // 3)
    uitdrukking_diepte = min(4, max(1, diepte - regels_aantal + 1))

    bekend = {}
    regels = []
    stappen = []
    for i in range(regels_aantal):
        naam = _NAMEN[i]
        tekst, _, waarde, node = _code_uitdrukking(uitdrukking_diepte, t, bekend)
        regels.append(f"{naam} = {tekst}")
        bekend[naam] = waarde
        # Regel voor regel nalopen zoals je een programma met de hand naloopt —
        # maar mét de berekening erbij. Alleen `naam = waarde` opschrijven
        # verstopt een som van meerdere stappen in één getal, en daar liep ze
        # op diepte 4 op vast.
        _uitwerken(node, stappen)
        stappen.append(f"{naam} = {waarde}")

    # Eén lus erbovenop zodra er ruimte voor is: dat maakt het een programma
    # in plaats van een rijtje sommen.
    laatste = _NAMEN[regels_aantal - 1]
    if diepte >= 4:
        rondes = t.geheel(2, 6)
        stap = t.geheel(1, 20)
        regels.append(f"for i in range({rondes}):")
        regels.append(f"    {laatste} = {laatste} + {stap}")
        oud = bekend[laatste]
        erbij = rondes * stap
        bekend[laatste] = oud + erbij
        stappen.append(f"{rondes} * {stap} = {erbij}")
        # De optelling stond er eerst níét — "b = 82" kwam uit het niets,
        # terwijl 72 + 10 = 82 de hele les is.
        stappen.append(f"{oud} + {erbij} = {bekend[laatste]}")
        stappen.append(f"{laatste} = {bekend[laatste]}")

    # Drie eindes. `print` met een kale naam was het enige einde, en dat liet
    # twee gaten die het bevroren proefwerk op 10 aug 2026 blootlegde: een
    # `print` met een sóm erin kende ze niet (ze schreef er dapper `b = 42`
    # bij een uitkomst van -42), en `if/else` bestond in haar wereld helemaal
    # niet. Stof die nergens in de wereld voorkomt kan ze alleen maar
    # verleren — de wereld hoort de taal van de grondslag te blijven spreken.
    #
    # Alleen tot en met diepte 5: dat is het bereik van de grondslag, en op
    # diepte 7–8 duwden de extra regels 40% van de opgaven het venster uit
    # (gemeten 10 aug 2026, past zakte van 85% naar 60%).
    einde = (t.keuze(("gewoon", "gewoon", "reken", "alsdan"))
             if diepte <= 5 else "gewoon")
    if einde != "gewoon" and len(bekend) < 2:
        # Voor een vergelijking of een som zijn twee namen nodig.
        naam2 = _NAMEN[len(bekend)]
        extra = t.geheel(1, 99)
        regels.append(f"{naam2} = {extra}")
        bekend[naam2] = extra
        stappen.append(f"{naam2} = {extra}")

    if einde == "reken":
        # print met een som erin — de uitkomst mag negatief zijn.
        na, nb = sorted(bekend)[-2:]
        op = t.keuze(("-", "-", "+"))
        waarde = bekend[na] - bekend[nb] if op == "-" else bekend[na] + bekend[nb]
        regels.append(f"print({na} {op} {nb})")
        stappen.append(f"{bekend[na]} {op} {bekend[nb]} = {waarde}")
        return "\n".join(regels), waarde, " ; ".join(stappen)

    if einde == "alsdan":
        na, nb = sorted(bekend)[-2:]
        wa, wb = bekend[na], bekend[nb]
        regels += [f"if {na} > {nb}:", f"    print({na} - {nb})",
                   "else:", f"    print({nb} - {na})"]
        if wa > wb:
            stappen.append(f"{wa} > {wb}, dus {na} - {nb}")
            waarde = wa - wb
            stappen.append(f"{wa} - {wb} = {waarde}")
        else:
            stappen.append(f"{wa} > {wb} is niet zo, dus {nb} - {na}")
            waarde = wb - wa
            stappen.append(f"{wb} - {wa} = {waarde}")
        return "\n".join(regels), waarde, " ; ".join(stappen)

    regels.append(f"print({laatste})")
    return "\n".join(regels), bekend[laatste], " ; ".join(stappen)


_MAKERS = {"rekenen": _rekenen, "puzzel": _rij, "code": _code}


# --- naar buiten -----------------------------------------------------------

def maak(familie, diepte, nummer):
    """Een taak uit de wereld. Volledig bepaald door de drie argumenten.

    De diepte komt in het `graad`-veld van de taak: het ís de moeilijkheid,
    alleen nu een schuif in plaats van een trede.
    """
    if familie not in FAMILIES:
        raise ValueError(f"onbekende familie {familie!r}; keuze uit {FAMILIES}")
    if not MINSTE_DIEPTE <= diepte <= MEESTE_DIEPTE:
        raise ValueError(
            f"diepte {diepte} valt buiten {MINSTE_DIEPTE}–{MEESTE_DIEPTE}"
        )
    t = Trekker(_zaad_van(familie, diepte, nummer))
    opgave, oplossing, uitwerking = _MAKERS[familie](diepte, t)
    if opgave is None:
        # Er is geen uitwerking die er uitkomt — dan valt er niets te leren,
        # alleen te raden. `leerreeks` slaat hem over.
        return None
    return Taak(familie=familie, graad=diepte, nummer=nummer,
                opgave=opgave, oplossing=str(oplossing), uitwerking=uitwerking)


def past(taak, ruimte=MEESTE_TEKENS):
    """Past deze opgave met zijn antwoord binnen het venster?

    Een taak die niet in het venster past kan ze niet eens lézen, en die moet
    dus niet in haar leerstof terechtkomen. Bij een grammatica die zichzelf
    dieper maakt is dat geen theoretisch geval: op diepte 12 kwamen er
    programma's uit van ruim vijfhonderd tekens.
    """
    return len(taak.opgave) + len(taak.te_leren()) + 3 <= ruimte


def leerreeks(familie, diepte, aantal, vanaf=0, ruimte=MEESTE_TEKENS,
              uitsluiten=None):
    """Leerstof uit de wereld.

    Slaat twee soorten taken over: wat niet in het venster past, en wat botst
    met een proefwerk. Dat tweede is dezelfde grendel als bij `taken.py` — op
    8 aug 2026 bleek daar een kwart van de leerstof dezelfde opgaven op te
    leveren als de meetlat, en niemand had het gezien.

    `uitsluiten` is een verzameling opgaveteksten die niet gebruikt mogen
    worden. `proefwerken.py` levert die aan; los gebruikt hij niets uit.
    """
    verboden = uitsluiten if uitsluiten is not None else frozenset()
    gevonden = []
    nummer = vanaf
    grens = vanaf + aantal * 20 + 1000
    while len(gevonden) < aantal:
        if nummer > grens:
            raise ValueError(
                f"{familie} diepte {diepte}: maar {len(gevonden)} van de "
                f"{aantal} gevraagde taken gevonden tussen {vanaf} en {nummer}"
            )
        taak = maak(familie, diepte, nummer)
        if taak is not None and past(taak, ruimte) and taak.opgave not in verboden:
            gevonden.append(taak)
        nummer += 1
    return gevonden
