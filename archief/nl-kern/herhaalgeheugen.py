"""
Het herhaalgeheugen — en de flessenhals waar U aan hangt.

Dit is de eerste versie van H. Wat hier in gaat, gaat door een vaste, smalle,
discrete doorgang; in fase 1 wijd open, in fase 4 geknepen. Cley heeft die
koppeling op 8 aug 2026 goedgekeurd.

WAAROM DE FLESSENHALS ER NU AL IN ZIT
-------------------------------------
Uit `CLAUDE.md`: *"Zit hij er vanaf het begin in, dan hoeft fase 4 hem alleen
te knijpen. Zit hij er niet in, dan moet al het geheugen van fase 1 tot 3
worden omgezet of weggegooid."* Zelfde categorie als determinisme.

En uit de redenering achter U: de druk moet echt zijn. *"De tekenset groeit
niet mee met de wereld, het aantal situaties wel. Dan is hergebruik van tekens
over situaties heen de enige manier om binnen de band te blijven."* In fase 1
is er nog geen druk — de doorgang is ruimer dan nodig. Maar het pad ligt er, en
knijpen is later één getal veranderen in plaats van een verbouwing.

DE GRENDEL
----------
Het geheugen bewaart **uitsluitend codes**, nooit de ervaring zelf. Wie iets
wil onthouden moet door `Flessenhals` heen; er is geen andere weg naar binnen.
Dat is met opzet: zou er een tweede ingang zijn, dan wordt die op de avond dat
de flessenhals knelt gebruikt, en dan is er van U niets meer over.

Past een ervaring niet door de doorgang, dan wordt hij **geweigerd**. In fase 1
gebeurt dat vrijwel nooit. In fase 4 is dat precies de druk die de notatie moet
laten ontstaan.
"""

import tekens

# Fase 1: wijd open. De tekenset is dezelfde als die van de kern, en 128 tekens
# is ruim het dubbele van wat een opgave met antwoord nodig heeft.
#
# Fase 4 knijpt deze twee getallen. Dát is het hele werk daar — niet het pad
# aanleggen, alleen het smaller maken.
TEKENS_IN_DE_SET = tekens.OMVANG
LENGTE = 128


class TePasseren(Exception):
    """Deze ervaring past niet door de doorgang."""


class Flessenhals:
    """De enige weg naar het geheugen.

    In fase 1 is de codering een omkeerbare afbeelding: er gaat niets verloren,
    want er is nog geen druk. De vórm is wat telt — een vaste tekenset en een
    vaste maximale lengte — want dat is wat fase 4 gaat knijpen.
    """

    def __init__(self, tekens_in_de_set=TEKENS_IN_DE_SET, lengte=LENGTE):
        self.tekens_in_de_set = tekens_in_de_set
        self.lengte = lengte

    def codeer(self, taak, gegeven_antwoord, goed):
        """Een ervaring wordt een reeks tekens. Meer dan dit gaat er niet in.

        Wat er in gaat is de opgave met het **juiste** antwoord, niet wat ze
        ervan maakte. De les is de correctie en niet haar poging; zou haar
        eigen antwoord er in gaan, dan oefent ze bij het herhalen haar fouten
        in. Wat ze zei is wel bekend — het bepaalt `goed` — maar het is geen
        herinnering waar je op terugkomt.

        Familie, graad en `goed` zijn de kaartjes op de la en gaan bewust niet
        door de doorgang: ze zeggen iets over de herinnering, niet over de
        wereld. Wat in fase 4 moet indikken is de inhoud.
        """
        # `te_leren()` en niet `oplossing`: de uitwerking is de les, niet het
        # kale getal. Stond hier alleen het antwoord, dan leert elke herinnering
        # haar juist het uitwerken over te slaan — en met 37,5% herhaling is dat
        # ruim een derde van alles wat ze ziet. Gevonden op 9 aug 2026, nadat ze
        # een nacht lang op moeilijkheid 4 bleef gokken terwijl ze het kón.
        ruw = ([tekens.VRAAG] + tekens.codeer(taak.opgave)
               + [tekens.ANTWOORD] + tekens.codeer(taak.te_leren())
               + [tekens.EIND])
        if len(ruw) > self.lengte:
            raise TePasseren(
                f"ervaring van {len(ruw)} tekens past niet door een doorgang "
                f"van {self.lengte}"
            )
        if any(c >= self.tekens_in_de_set for c in ruw):
            raise TePasseren(
                f"ervaring gebruikt een teken buiten de set van "
                f"{self.tekens_in_de_set}"
            )
        return {
            "code": ruw,
            "familie": taak.familie,
            "graad": taak.graad,
            # None betekent: niet nagekeken. Dat is iets anders dan fout, en
            # het door elkaar halen zou het beeld van hoe goed ze het doet
            # stilletjes vertekenen.
            "goed": None if goed is None else bool(goed),
        }

    def ontcijfer(self, opgeslagen):
        """Terug van code naar iets bruikbaars.

        In fase 4, als de codering lossy wordt, komt hier niet meer de
        oorspronkelijke tekst uit maar wat ze ervan onthouden heeft. De
        aanroepers moeten daar nu al tegen kunnen.
        """
        codes = opgeslagen["code"]
        try:
            scheiding = codes.index(tekens.ANTWOORD)
        except ValueError:
            return {"opgave": "", "oplossing": "", **opgeslagen}
        return {
            "opgave": tekens.decodeer(codes[1:scheiding]),
            "oplossing": tekens.antwoord_uit_reeks(codes),
            "familie": opgeslagen["familie"],
            "graad": opgeslagen["graad"],
            "goed": opgeslagen["goed"],
        }

    def bezetting(self, opgeslagen):
        """Hoeveel van de doorgang wordt er gebruikt?

        Dit is het getal dat fase 4 gaat knijpen. Zolang het ver onder de 1
        blijft is er geen druk, en dus geen reden voor haar om iets te
        verzinnen.
        """
        return len(opgeslagen["code"]) / self.lengte


class Herhaalgeheugen:
    """Een voorraad ervaringen om op terug te komen.

    Bewaart uitsluitend wat er door de flessenhals is gekomen. Loopt hij vol,
    dan verdwijnt het oudste — dat is voor fase 1 goed genoeg en het is een van
    de eerste dingen die fase 4 zal willen vervangen door iets dat kiest wat
    het waard is om te houden.
    """

    def __init__(self, ruimte=20000, flessenhals=None):
        self.ruimte = ruimte
        self.flessenhals = flessenhals or Flessenhals()
        self._inhoud = []
        self._telling = {}
        self.geweigerd = 0

    def onthoud(self, taak, antwoord, goed):
        try:
            opgeslagen = self.flessenhals.codeer(taak, antwoord, goed)
        except TePasseren:
            self.geweigerd += 1
            return False
        self._inhoud.append(opgeslagen)
        vakje = (opgeslagen["familie"], opgeslagen["graad"])
        self._telling[vakje] = self._telling.get(vakje, 0) + 1
        if len(self._inhoud) > self.ruimte:
            self._vergeet_een()
        return True

    def _vergeet_een(self):
        """Evenwichtig vergeten — de eerste voorproef van fase 4.

        De eerste versie gooide botweg het oudste weg. Gemeten op 10 aug 2026
        (stap 102.000): de hele voorraad bestond toen uit de vakjes van de
        laatste ~600 stappen — zeldzame vakjes waren op drie of vier
        herinneringen na verdwenen, en wat er niet in zit kan de herhaling
        niet beschermen. Nu wijkt het oudste uit het gróótste vakje: zeldzaam
        houdt een bodem, veelvoorkomend blijft vers. Binnen een vakje blijft
        het vergeten gewoon oud-eerst.

        Deterministisch, ook bij gelijke stand: er wordt op (aantal, vakje)
        gekozen, dus dezelfde stroom geeft altijd hetzelfde geheugen.
        """
        grootste = max(self._telling.items(), key=lambda kv: (kv[1], kv[0]))[0]
        for i, o in enumerate(self._inhoud):
            if (o["familie"], o["graad"]) == grootste:
                del self._inhoud[i]
                break
        self._telling[grootste] -= 1
        if not self._telling[grootste]:
            del self._telling[grootste]

    def herhaal(self, hoeveel, trekker):
        """Haal ervaringen op om opnieuw langs te gaan.

        `trekker` bepaalt welke — meegegeven en niet zelf verzonnen, zodat de
        keuze uit (zaad, stapnummer) volgt en de hele stroom herhaalbaar blijft.
        """
        if not self._inhoud:
            return []
        gekozen = [self._inhoud[trekker.geheel(0, len(self._inhoud) - 1)]
                   for _ in range(min(hoeveel, len(self._inhoud)))]
        return [self.flessenhals.ontcijfer(o) for o in gekozen]

    def __len__(self):
        return len(self._inhoud)

    # --- mee in de momentopname -------------------------------------------
    # N: "Haar toestand is meer dan gewichten: ook haar aangegroeide geheugen."
    # Op 9 aug 2026 bleek dat het geheugen níét meeging: na de crash van de
    # X399 hervatte de run met haar kunnen intact en haar 20.000 herinneringen
    # weg — een stille geheugenwissing bij elke herstart.

    def neem_mee(self):
        """Alles wat nodig is om dit geheugen exact terug te bouwen.

        Alleen lijsten en getallen, niets apparaatgebonden — dezelfde eis als
        bij de rest van het checkpoint, zodat het een verhuizing overleeft.
        """
        return {
            "ruimte": self.ruimte,
            "geweigerd": self.geweigerd,
            "inhoud": [dict(o) for o in self._inhoud],
        }

    def zet_terug(self, meegenomen):
        """Zet een meegenomen geheugen exact terug."""
        self.ruimte = int(meegenomen["ruimte"])
        self.geweigerd = int(meegenomen["geweigerd"])
        self._inhoud = [dict(o) for o in meegenomen["inhoud"]]
        # De telling staat niet in het checkpoint maar volgt uit de inhoud —
        # zo kan een checkpoint van vóór het evenwichtig vergeten er gewoon in.
        self._telling = {}
        for o in self._inhoud:
            vakje = (o["familie"], o["graad"])
            self._telling[vakje] = self._telling.get(vakje, 0) + 1
        return len(self._inhoud)

    def stand(self):
        """Wat er in zit, en hoe vol de doorgang zit."""
        if not self._inhoud:
            return {"aantal": 0, "geweigerd": self.geweigerd,
                    "bezetting_gemiddeld": None, "bezetting_hoogste": None}
        bezetting = [self.flessenhals.bezetting(o) for o in self._inhoud]
        nagekeken = [o["goed"] for o in self._inhoud if o["goed"] is not None]
        return {
            "aantal": len(self._inhoud),
            "geweigerd": self.geweigerd,
            "bezetting_gemiddeld": sum(bezetting) / len(bezetting),
            "bezetting_hoogste": max(bezetting),
            "nagekeken": len(nagekeken),
            "goed_deel": (sum(nagekeken) / len(nagekeken)) if nagekeken else None,
        }
