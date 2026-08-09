"""
De leerlus — waar de kern werkelijk gaat leren.

Brengt samen wat er los al staat: het netwerk, de taken met hun meetlat, het
herhaalgeheugen met de flessenhals, de nieuwsgierigheid die kiest waar ze aan
werkt, en het logboek eronder.

De `Leerder` past op de twee dingen die de meetlus vraagt — `antwoord(taak)` en
`leer(taken)` — zodat de C-meting hem zonder meer aankan.

DRIE DINGEN DIE HIER GOED MOETEN
--------------------------------
**De fout telt alleen over het antwoord.** Het masker uit `tekens.py` zorgt
daarvoor. Één positie verschuiven en ze leert vragen voorspellen in plaats van
beantwoorden, en dat ziet er in de foutcurve prima uit.

**Antwoorden gebeurt in één partij tegelijk.** Honderd taken los afgaan is
honderd keer door het netwerk; samen is het één keer. Dat maakt het verschil
tussen meten dat kan wanneer je wilt en meten dat je gaat vermijden.

**Herhaling staat standaard uit.** Dat is opzet: eerst moet de nulmeting van C
er zijn — hoe erg vergeet ze zónder iets ertegen. Zet je het meteen aan, dan
weet je nooit hoe groot het probleem was en dus ook niet of je het hebt
opgelost of alleen bedekt.
"""

import threading

import determinisme
import proefwerken
import taken as taken_module
import tekens
import torch
import torch.nn.functional as F
import wereld
from herhaalgeheugen import Herhaalgeheugen
from netwerk import Kern
from nieuwsgierigheid import Nieuwsgierigheid

# Hoeveel tekens ze mag schrijven voor een antwoord.
#
# Geen detail. Met 48 paste vanaf diepte 4 **geen enkele** uitwerking:
# gemiddeld 58 tekens op diepte 4, 75 op 5, 91 op 6. Ze werd dus altijd
# afgekapt, en het nakijken pakte een tussenstap als eindantwoord. Dat zag
# eruit alsof ze het antwoord gokte terwijl ze er de ruimte niet voor had.
#
# 128 dekt diepte 6 met marge. Elk teken is een doorgang door het netwerk, dus
# ruimer kost tijd — maar te krap kost de meting, en dat is erger.
RUIMTE = 128

# partij × lengte² per stuk; ~64 reeksen van 280 tekens tegelijk
_STUK_BUDGET = 5_000_000


def bf16_bruikbaar(apparaat):
    """Heeft deze kaart bf16 in hardware?

    **Niet** `torch.cuda.is_bf16_supported()` gebruiken: die gaf op de P100 ook
    `True` terwijl bf16 daar geëmuleerd werd en trager was dan fp32. Gemeten op
    8 aug 2026. De generatie van de kaart is het eerlijke antwoord — vanaf 8.0
    (Ampere) zitten er tensor cores in die het echt kunnen.
    """
    if not str(apparaat).startswith("cuda") or not torch.cuda.is_available():
        return False
    groot, _ = torch.cuda.get_device_capability(0)
    return groot >= 8


def ruimte_voor(diepte, familie=None):
    """Hoeveel tekens een uitwerking hier nodig heeft.

    **Per familie, niet alleen per diepte.** De eerste versie was geijkt op
    rekenen, waar de uitwerking met de diepte meegroeit: 50 tekens op diepte 3,
    110 op 6. Bij puzzels klopt dat niet — daar staan altijd zes verschillen
    onder elkaar, dus een uitwerking is rond de 90 tekens, óók op diepte 1.

    Met de rekenmaat kreeg puzzel diepte 1 dus 34 tekens voor een uitwerking
    van 89. Ze werd overal afgekapt en scoorde nul op haar hele familie, terwijl
    ze het wel degelijk leerde. Gevonden op 9 aug 2026.
    """
    if familie == "puzzel":
        # Groeit hard met de diepte: langste uitwerking 104 tekens op diepte 2,
        # 257 op 3, 302 op 5 — want de methode zet zichzelf door tot hij
        # uitkomt. Te krap kost de hele familie, zoals op 9 aug 2026 bleek.
        return min(336, 80 * diepte + 48)
    if familie == "code":
        # Sinds de uitwerking élke stap laat zien (9 aug 2026): langste 109 op
        # diepte 4, 177 op 5, 281 op 6. Daarvoor was het één regel per
        # variabele en leek 88 genoeg — en bleef ze plat op 1% omdat de les
        # zelf onvolledig was.
        if diepte <= 2:
            return 24
        return min(320, 96 * (diepte - 3) + 48)
    # Rekenen. Langste uitwerking: 50 op diepte 3, 110 op 6, 180 op 9, 247 op
    # 12, en gemeten op 9 aug 2026: 294 op 14, 356 op 16, 384 op 17. De oude
    # grens van 280 kapte diepte 14+ dus af — zelfde fout als bij puzzel en
    # code. 384 plus de langste opgave op 17 (102 tekens) blijft binnen het
    # venster van 512.
    return min(384, 20 * diepte + 24)


class Leerder:
    def __init__(self, kern=None, apparaat=None, leersnelheid=3e-4,
                 partij=32, herhaling=0.375, remkracht=0.0, geheugen=None,
                 nieuwsgierig=None, diepste=2, rand_drempel=0.5,
                 proberen_elke=4, bf16=None):
        self.apparaat = apparaat or ("cuda" if torch.cuda.is_available() else "cpu")
        self.kern = (kern or Kern()).to(self.apparaat)
        self.bf16 = bf16_bruikbaar(self.apparaat) if bf16 is None else bf16

        # Beide kaarten. Ze kunnen elkaars geheugen niet bereiken (geen NVLink
        # op de PCIe-uitvoering), dus de partij wordt gesplitst en de
        # gradiënten gaan over de PCIe-bus samen. Bij 14 miljoen parameters is
        # dat ruim de moeite waard.
        #
        # `self.kern` blijft het kale netwerk: het checkpoint mag geen weet
        # hebben van hoeveel kaarten er toevallig in de machine zitten. Dat is
        # dezelfde eis als "toestand hardware-onafhankelijk opslaan".
        self._rekenkern = self.kern
        self._antwoordkern = self.kern
        self._antwoordapparaat = self.apparaat
        self._gewichten_vers = True

        if self.apparaat == "cuda" and torch.cuda.device_count() > 1:
            self._rekenkern = torch.nn.DataParallel(self.kern)

            # Antwoorden gebeurt op de tweede kaart. Twee redenen:
            #
            # Het is inmiddels het duurste deel — één doorgang per teken — en
            # het draaide volledig op kaart 0, die met DataParallel toch al de
            # hoofdkopie en alle verzamelde uitvoer draagt. Cley zag dat als
            # 4670 MB tegen 1336 MB.
            #
            # En DataParallel is hier juist verkeerd: die kopieert de gewichten
            # bij elke aanroep opnieuw naar beide kaarten, en bij tachtig
            # tekens achter elkaar zijn dat tachtig kopieën van 57 MB. Eén
            # eigen kopie op kaart 1, bijgewerkt zodra de gewichten veranderd
            # zijn, is veel goedkoper.
            self._antwoordapparaat = "cuda:1"
            self._antwoordkern = Kern.uit_vorm(self.kern.vorm()).to("cuda:1")
            self._antwoordkern.eval()

        self.optimizer = torch.optim.AdamW(self.kern.parameters(), lr=leersnelheid)
        self.partij = partij
        self.herhaling = herhaling          # deel van elke partij uit het geheugen
        self.remkracht = remkracht          # hoe hard belangrijke gewichten remmen
        self.geheugen = geheugen if geheugen is not None else Herhaalgeheugen()
        self.stappen = 0

        # De rand van haar wereld, per familie apart. Groeit mee zodra ze die
        # familie op de huidige rand aankan — zie open_dieper().
        self.diepste_per = {f: diepste for f in wereld.FAMILIES}
        self.rand_drempel = rand_drempel
        # Om de hoeveel stappen ze eerst zelf probeert. Niet élke stap: het
        # schrijven van een antwoord kost drie keer zoveel als de leerstap
        # eromheen, en de nieuwsgierigheid heeft die score niet zo vaak nodig.
        #
        # En dan meteen de héle partij, niet een steekproef: 128 taken
        # beantwoorden kost even veel als 16. De tijd hangt aan het aantal
        # tekens dat ze schrijft, niet aan hoeveel taken er tegelijk in gaan.
        self.proberen_elke = proberen_elke
        self.nieuwsgierig = nieuwsgierig or Nieuwsgierigheid(
            families=wereld.FAMILIES,
            graden=tuple(range(wereld.MINSTE_DIEPTE, diepste + 1)),
        )

        # De rem: waar de gewichten stonden toen er iets geconsolideerd werd,
        # en hoe belangrijk elk gewicht toen bleek.
        self._anker = None
        self._belang = None

    # --- de rem: belangrijke gewichten vastzetten -------------------------

    def consolideer(self, taken_, partijen=40):
        """Stel vast welke gewichten er voor deze stof toe deden.

        Voor elk gewicht wordt gemeten hoe sterk de fout erop reageert — het
        kwadraat van de gradiënt, gemiddeld over een aantal partijen. Gewichten
        waar de fout gevoelig voor is, waren blijkbaar belangrijk; die worden
        daarna afgeremd.

        Kost één keer een paar partijen rekenwerk, en daarna per stap alleen
        nog een vermenigvuldiging per gewicht. **Het kost geen plaats in de
        partij** — dat is precies waarin dit van herhaling verschilt.

        Waar dit op stukloopt: er moet een moment zijn waarop je consolideert,
        dus er moeten grenzen tussen onderwerpen zijn. In een open wereld (F)
        zijn die er niet vanzelf. Dat is geen detail maar de reden dat deze
        aanpak niet zomaar meeschaalt naar wat er later komt.
        """
        self.kern.train()
        nieuw_belang = {n: torch.zeros_like(p)
                        for n, p in self.kern.named_parameters()}

        gedaan = 0
        for begin in range(0, len(taken_), self.partij):
            if gedaan >= partijen:
                break
            brokje = list(taken_[begin:begin + self.partij])
            if not brokje:
                continue
            codes, masker = self._partij_maken(brokje)
            scores = self._rekenkern(codes)
            voorspeld = scores[:, :-1].reshape(-1, tekens.OMVANG)
            doel = codes[:, 1:].reshape(-1)
            meetellen = masker[:, 1:].reshape(-1)
            fout = F.cross_entropy(voorspeld[meetellen], doel[meetellen])

            self.kern.zero_grad(set_to_none=True)
            fout.backward()
            for naam, p in self.kern.named_parameters():
                if p.grad is not None:
                    nieuw_belang[naam] += p.grad.detach() ** 2
            gedaan += 1

        if gedaan == 0:
            return None
        for naam in nieuw_belang:
            nieuw_belang[naam] /= gedaan

        # Optellen bij wat er al stond: eerdere stof blijft ook belangrijk.
        # Het anker verschuift wél naar hier — remmen doe je naar waar je nú
        # staat, niet naar waar je ooit stond.
        if self._belang is None:
            self._belang = nieuw_belang
        else:
            for naam in nieuw_belang:
                self._belang[naam] = self._belang[naam] + nieuw_belang[naam]
        self._anker = {n: p.detach().clone()
                       for n, p in self.kern.named_parameters()}
        self.kern.zero_grad(set_to_none=True)
        return {"partijen": gedaan,
                "belang_gemiddeld": float(sum(b.sum() for b in self._belang.values()))}

    def _remboete(self):
        """Hoe ver staan de gewichten van hun anker, gewogen naar belang."""
        if self._anker is None or self.remkracht <= 0:
            return None
        boete = None
        for naam, p in self.kern.named_parameters():
            deel = (self._belang[naam] * (p - self._anker[naam]) ** 2).sum()
            boete = deel if boete is None else boete + deel
        return 0.5 * self.remkracht * boete

    # --- antwoorden --------------------------------------------------------

    @torch.no_grad()
    def antwoorden(self, taken_, hoogstens=RUIMTE):
        """Beantwoord een reeks taken in één partij.

        `hoogstens` moet ruim genoeg zijn voor een hele uitwerking. Met 24 kon
        ze haar som niet afmaken en telde elk antwoord als fout, hoe goed ze
        ook rekende.

        Rechts opvullen en per taak bijhouden hoe ver hij is. Dat kan omdat de
        aandacht causaal is: de laatste echte positie kijkt nooit naar de
        opvulling erachter. Links opvullen zou hier niet werken zonder de
        plaatsen te verschuiven.
        """
        kernen = self._antwoordkernen()
        if len(kernen) == 1 or len(taken_) < 2 * len(kernen):
            kern, apparaat = kernen[0]
            return self._antwoorden_op(taken_, kern, apparaat, hoogstens)

        # Over beide kaarten tegelijk. Elke draad rijdt zijn eigen kaart met
        # zijn eigen kopie van het netwerk; torch laat de GIL los tijdens het
        # rekenen, dus ze lopen werkelijk naast elkaar.
        #
        # Eerder deed kaart 1 het antwoorden terwijl kaart 0 stilstond, en
        # andersom bij het leren — om de beurt dus, niet tegelijk.
        deel = (len(taken_) + len(kernen) - 1) // len(kernen)
        stukken = [taken_[i * deel:(i + 1) * deel] for i in range(len(kernen))]
        uitkomsten = [None] * len(kernen)

        def doe(i):
            kern, apparaat = kernen[i]
            uitkomsten[i] = self._antwoorden_op(stukken[i], kern, apparaat,
                                                hoogstens)

        draden = [threading.Thread(target=doe, args=(i,))
                  for i in range(len(kernen)) if stukken[i]]
        for d in draden:
            d.start()
        for d in draden:
            d.join()
        return [a for stuk in uitkomsten if stuk for a in stuk]

    def _antwoordkernen(self):
        """De netwerkkopieën waarop geantwoord kan worden, per kaart één.

        De kopie op kaart 1 wordt bijgewerkt zodra er sinds de vorige keer
        geleerd is: één keer 57 MB over de bus. DataParallel zou dat bij élk
        teken opnieuw doen, en dat zijn er tachtig achter elkaar.
        """
        if self._antwoordkern is self.kern:
            return [(self.kern, self.apparaat)]
        if self._gewichten_vers:
            self._antwoordkern.load_state_dict(self.kern.state_dict())
            self._gewichten_vers = False
        return [(self.kern, self.apparaat),
                (self._antwoordkern, self._antwoordapparaat)]

    @torch.no_grad()
    def _antwoorden_op(self, taken_, kern, apparaat, hoogstens):
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=self.bf16):
            return self._antwoorden_echt(taken_, kern, apparaat, hoogstens)

    @torch.no_grad()
    def _antwoorden_echt(self, taken_, kern, apparaat, hoogstens):
        """De eigenlijke lus, op één kaart."""
        kern.eval()
        aanzetten = [tekens.vraag_naar_reeks(t) for t in taken_]
        langste = max(len(a) for a in aanzetten)
        # Inkorten in plaats van omvallen: een te lange opgave hoort een lager
        # cijfer op te leveren, niet een gestrande meting.
        ruimte = kern.venster - langste
        if ruimte < 4:
            raise ValueError(
                f"opgave van {langste} tekens laat geen ruimte over om te "
                f"antwoorden binnen een venster van {kern.venster}")
        hoogstens = min(hoogstens, ruimte)

        # **Links** opvullen, niet rechts. Alle vragen eindigen dan op dezelfde
        # plaats, en dat is wat de cache mogelijk maakt: er komt één teken per
        # keer bij, voor iedereen op dezelfde plek. Bij rechts opvullen zou de
        # cache voor korte vragen vol opvulling staan.
        vraag = torch.full((len(taken_), langste), tekens.VUL,
                           dtype=torch.long, device=apparaat)
        for i, aanzet in enumerate(aanzetten):
            vraag[i, langste - len(aanzet):] = torch.tensor(aanzet, device=apparaat)
        masker = vraag == tekens.VUL           # hier staat niets echts

        # De vraag in één doorgang; daarna alleen nog het nieuwe teken.
        scores, cache = kern.vooruit(vraag, sleutelmasker=masker)
        geschreven = []
        klaar = torch.zeros(len(taken_), dtype=torch.bool, device=apparaat)
        volgende = scores[:, -1].argmax(dim=-1)

        for stap in range(hoogstens):
            volgende = torch.where(klaar,
                                   torch.full_like(volgende, tekens.VUL),
                                   volgende)
            geschreven.append(volgende)
            klaar = klaar | (volgende == tekens.EIND)
            if bool(klaar.all()) or stap == hoogstens - 1:
                break
            masker = torch.cat(
                (masker, torch.zeros_like(masker[:, :1])), dim=1)
            scores, cache = kern.vooruit(volgende[:, None], cache=cache,
                                         vanaf=langste + stap,
                                         sleutelmasker=masker)
            volgende = scores[:, -1].argmax(dim=-1)

        antwoorden = torch.stack(geschreven, dim=1).tolist()
        return [tekens.antwoord_uit_reeks([tekens.ANTWOORD] + rij)
                for rij in antwoorden]

    def antwoord(self, taak):
        return self.antwoorden([taak])[0]

    # --- leren -------------------------------------------------------------

    def _partij_maken(self, brokje):
        reeksen, maskers = [], []
        for t in brokje:
            reeks, masker = tekens.taak_naar_reeks(t)
            reeksen.append(reeks)
            maskers.append(masker)
        reeksen, maskers = tekens.bundel(reeksen, maskers)
        codes = torch.tensor(reeksen, dtype=torch.long, device=self.apparaat)
        masker = torch.tensor(maskers, dtype=torch.bool, device=self.apparaat)
        return codes, masker

    def _stap(self, brokje):
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=self.bf16):
            return self._stap_echt(brokje)

    def _stap_echt(self, brokje):
        self.kern.train()
        codes, masker = self._partij_maken(brokje)
        n, lengte = codes.shape

        # Geheugenbudget (9 aug 2026): aandacht kost partij × lengte², en toen
        # de diepe stof openging (reeksen van ~460 tekens) liep de 8 GB-kaart
        # van de X399 vierendertig keer achter elkaar uit zijn geheugen. Zelfde
        # som, in stukken: de gradiënten tellen op over de stukken heen, dus de
        # uitkomst is wiskundig gelijk aan één grote partij — alleen het
        # geheugen blijft begrensd. De stukgrootte hangt alleen van (n, lengte)
        # af en is dus net zo herhaalbaar als de rest.
        stuk = max(1, min(n, _STUK_BUDGET // max(1, lengte * lengte)))

        self.optimizer.zero_grad(set_to_none=True)
        totaal_tellen = int(masker[:, 1:].sum())
        totaal_fout = 0.0
        for i in range(0, n, stuk):
            c = codes[i:i + stuk]
            m = masker[i:i + stuk]
            scores = self._rekenkern(c)
            # De score op plaats j voorspelt het teken op j+1. Het masker hoort
            # dus één op te schuiven; één positie mis en ze leert de vraag
            # voorspellen.
            voorspeld = scores[:, :-1].reshape(-1, tekens.OMVANG)
            doel = c[:, 1:].reshape(-1)
            meetellen = m[:, 1:].reshape(-1)
            som = F.cross_entropy(voorspeld[meetellen], doel[meetellen],
                                  reduction="sum")
            (som / max(1, totaal_tellen)).backward()
            totaal_fout += float(som.item())
        gemeten = totaal_fout / max(1, totaal_tellen)

        boete = self._remboete()
        if boete is not None:
            boete.backward()

        torch.nn.utils.clip_grad_norm_(self.kern.parameters(), 1.0)
        self.optimizer.step()
        self.stappen += 1
        self._gewichten_vers = True
        # De gemeten fout is die zónder de rem: anders lijkt de rem het leren
        # te verslechteren terwijl het alleen een andere grootheid is.
        return gemeten

    @property
    def nieuw_per_partij(self):
        """Hoeveel nieuwe taken er in een partij passen.

        De partij blijft altijd even groot. Herhaling gaat dus **ten koste van**
        nieuw materiaal en komt er niet bovenop — anders vergelijk je een run
        met meer rekenwerk tegen een run met minder, en meet je de hoeveelheid
        in plaats van het mechanisme. Die fout zat in de eerste nulmeting van
        8 aug 2026.
        """
        if self.herhaling <= 0:
            return self.partij
        return max(1, self.partij - int(self.partij * self.herhaling))

    def leer(self, taken_, onthouden=True):
        """Leer van een reeks taken. Voldoet aan wat de meetlus vraagt.

        Wat er geleerd wordt gaat ook het geheugen in, door de flessenhals.
        Zonder dat blijft het geheugen leeg en doet herhaling niets — dan lijkt
        een vergelijking mét en zónder herhaling iets te zeggen terwijl beide
        kanten hetzelfde doen.
        """
        fouten = []
        stap_grootte = self.nieuw_per_partij
        for begin in range(0, len(taken_), stap_grootte):
            brokje = list(taken_[begin:begin + stap_grootte])
            if onthouden:
                for t in brokje:
                    self.geheugen.onthoud(t, t.oplossing, None)
            if self.herhaling > 0 and len(self.geheugen):
                ruimte = self.partij - len(brokje)
                trekker = taken_module.Trekker(
                    determinisme.zaad_voor_stap(self.stappen))
                for oud in self.geheugen.herhaal(ruimte, trekker):
                    hervonden = _als_taak(oud)
                    if hervonden is not None:
                        brokje.append(hervonden)
            if brokje:
                fouten.append(self._stap(brokje))
        return sum(fouten) / len(fouten) if fouten else None

    # --- de lange lus ------------------------------------------------------

    def open_dieper(self, stap):
        """Zet de wereld dieper open zodra ze de rand aankan — per familie.

        Zonder rand zwerft ze meteen op diepte 12 rond, waar ze niets kan en
        dus ook niets leert. Met een rand die meegroeit ligt de wereld altijd
        net boven wat ze kan.

        **Per familie en niet in één keer voor alles.** De eerste opzet eiste
        dat ze álle drie de families op de huidige diepte aankon. Op 8 aug 2026
        bleef rekenen op 4% steken terwijl code op 100% zat — en daardoor bleef
        de hele wereld dicht, ook voor code. Eén trage familie hoort de andere
        niet op te sluiten.

        Terugdraaien gebeurt niet. Wat open is blijft open; zakt ze weg, dan
        trekt de nieuwsgierigheid haar er vanzelf weer heen.
        """
        opengegaan = []
        for familie in wereld.FAMILIES:
            rand = self.diepste_per[familie]
            if rand >= wereld.meeste_diepte(familie):
                continue
            if self.nieuwsgierig.score.get((familie, rand), 0.0) < self.rand_drempel:
                continue
            self.diepste_per[familie] = rand + 1
            self.nieuwsgierig.voeg_toe((familie, rand + 1), stap)
            opengegaan.append((familie, rand + 1))
        return opengegaan

    @property
    def diepste(self):
        """De diepste laag die ergens open staat — alleen om te melden."""
        return max(self.diepste_per.values())

    def werk(self, stap):
        """Eén stap van de lange lus: zelf kiezen, oefenen, onthouden.

        Dit is wat er 's nachts gebeurt. Welk onderwerp, welke taken en welke
        herhalingen volgen allemaal uit `(zaad, stapnummer)`, dus de hele
        stroom is herhaalbaar.
        """
        determinisme.begin_stap(stap)
        trekker = taken_module.Trekker(determinisme.zaad_voor_stap(stap))

        familie, diepte = self.nieuwsgierig.kies(stap, trekker)
        vanaf = trekker.geheel(0, 500_000)
        try:
            brokje = wereld.leerreeks(familie, diepte, self.partij, vanaf=vanaf,
                                      uitsluiten=proefwerken.stof())
        except ValueError:
            # Een diepte zonder genoeg opgaven mag nooit de run doden.
            # Nieuwsgierigheid ernaar dooft (score 1: niets meer te halen), de
            # rand klapt terug, en deze stap wordt overgeslagen.
            self.nieuwsgierig.bijgewerkt((familie, diepte), 1.0, stap)
            if self.diepste_per.get(familie, 0) >= diepte:
                self.diepste_per[familie] = max(1, diepte - 1)
            self.stappen += 1
            return {"stap": stap, "familie": familie, "diepte": diepte,
                    "score": None, "fout": None, "overgeslagen": True,
                    "diepste_per": dict(self.diepste_per), "dieper": []}

        # Om de zoveel stappen kijken wat ze er nú van maakt — dat stuurt de
        # nieuwsgierigheid en dat gaat het geheugen in.
        #
        # Niet elke stap: een antwoord schrijven kost drie keer zoveel als de
        # leerstap eromheen. En dan meteen de héle partij, want 128 taken
        # beantwoorden kost even veel als 16: de tijd hangt aan het aantal
        # tekens dat ze schrijft, niet aan hoeveel taken erin gaan.
        score = None
        if stap % self.proberen_elke == 0:
            gegeven = self.antwoorden(brokje,
                                      hoogstens=ruimte_voor(diepte, familie))
            goed = [t.nakijk(a) for t, a in zip(brokje, gegeven)]
            for t, a, g in zip(brokje, gegeven, goed):
                self.geheugen.onthoud(t, a, g)
            score = sum(goed) / len(goed)
            self.nieuwsgierig.bijgewerkt((familie, diepte), score, stap)

        fout = self.leer(brokje)
        dieper = self.open_dieper(stap)
        return {"stap": stap, "familie": familie, "diepte": diepte,
                "score": score, "fout": fout,
                "diepste_per": dict(self.diepste_per), "dieper": dieper}

    # --- toestand ----------------------------------------------------------

    def vorm(self):
        return self.kern.vorm()

    # --- haar hele toestand mee in de momentopname ------------------------
    # N: "Haar toestand is meer dan gewichten." Wat hier niet in zit, is na
    # een herstart stilzwijgend weg — zoals haar geheugen bij de crash van
    # 9 aug 2026.

    def neem_mee(self):
        return {
            "geheugen": self.geheugen.neem_mee(),
            "nieuwsgierig": self.nieuwsgierig.neem_mee(),
            "diepste_per": dict(self.diepste_per),
        }

    def zet_terug(self, meegenomen):
        if not meegenomen:
            return
        if meegenomen.get("geheugen"):
            self.geheugen.zet_terug(meegenomen["geheugen"])
        if meegenomen.get("nieuwsgierig"):
            self.nieuwsgierig.zet_terug(meegenomen["nieuwsgierig"])
        if meegenomen.get("diepste_per"):
            # begrensd terugzetten: een checkpoint kan een wereld dragen die
            # te diep open stond (code tot 12, vóór de grens van 8 bestond)
            self.diepste_per = {f: min(d, wereld.meeste_diepte(f))
                                for f, d in meegenomen["diepste_per"].items()}


def _als_taak(ontcijferd):
    """Maak van een herinnering weer iets waar op geoefend kan worden.

    In fase 1 is de codering omkeerbaar en komt de taak er heel uit. Zodra de
    flessenhals in fase 4 knijpt, komt hier niet meer de oorspronkelijke opgave
    uit maar wat ze ervan onthouden heeft — en dan is dit de plek waar dat
    verschil zichtbaar wordt.
    """
    if not ontcijferd["opgave"]:
        return None
    # Wat er uit het geheugen komt ís de uitwerking; het antwoord is het
    # laatste getal daarin. Zo leert ze bij het herhalen hetzelfde als bij het
    # eerste keer zien, en niet een kortere weg.
    geheel = ontcijferd["oplossing"]
    getallen = taken_module._GETAL.findall(geheel)
    return taken_module.Taak(
        familie=ontcijferd["familie"],
        graad=ontcijferd["graad"],
        nummer=-1,                       # herinnering, geen taak uit de voorraad
        opgave=ontcijferd["opgave"],
        oplossing=getallen[-1] if getallen else geheel,
        uitwerking=geheel if "=" in geheel else None,
    )
