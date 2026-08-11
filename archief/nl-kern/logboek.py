"""
Het logboek — zo weinig mogelijk kwijtraken.

De roadmap schrijft dit ontwerp voor bij N:

    "Scheid het logboek van de momentopname. Volledige opnames zijn duur, dus
    die maak je zelden; alles wat daarna gebeurt schrijf je doorlopend weg in
    een logboek dat je alleen aanvult. Bij opstarten laad je de opname en speel
    je het logboek erover af. Verlies: seconden in plaats van uren."

WAT ER IN MOET, EN WAT NIET
---------------------------
Omdat alles deterministisch uit (zaad, stapnummer) volgt, hoeft hier niet in
wat er gerékend is — een stap opnieuw doen geeft per definitie hetzelfde
resultaat. Wat er wél in moet is alles wat níét af te leiden valt:

  * hoe ver we waren toen het misging
  * wat er van buiten kwam: wat Cley zei, wat er waargenomen is, wat er van
    internet kwam. Dat is nergens uit terug te rekenen
  * uitkomsten die je niet opnieuw wilt moeten verdienen, zoals meetwaarden

Dat scheelt het verschil tussen megabytes per uur en kilobytes.

DE TWEE VALLEN UIT DE ROADMAP
-----------------------------
1. "Linux meldt dat je geschreven hebt lang voordat er iets op schijf staat —
   met 472 GB bufferen ze gigabytes." Daarom wordt hier geforceerd naar schijf
   gefsynct. Niet na elke regel: dat kost op een SSD zonder power-loss
   protection meer dan het waard is. Wel minstens elke `fsync_tussenpoos`
   seconden, en altijd bij een nette afsluiting. Dat maakt de belofte waar die
   er staat — verlies in seconden, niet in uren.

2. De momentopname zelf wordt atomair omgewisseld; zie checkpoint.py.

DE TELLING — één afspraak, en houd je eraan
-------------------------------------------
Een momentopname met `stap=N` betekent: **N stappen gedaan, de volgende is
nummer N.** De opname bevat dus de toestand ná stap N-1.

Een logboekregel met `stap=k` betekent: **stap k is uitgevoerd.**

Daaruit volgt dat regels met k < N in de opname zitten en regels met k >= N
niet. Overal waar hier op stapnummer gefilterd wordt, is de grens dus `>= N`
en niet `> N`. Die ene positie schelen betekent dat elke herstart stilzwijgend
één stap werk weggooit — het soort fout dat pas weken later opvalt, en dan in
de metingen en niet in een foutmelding. Op 8 aug 2026 zat hij er in en is hij
door de toets gevangen.

TWEE SOORTEN STILTE
-------------------
"Aangekondigd afsluiten omdat jij weggaat is rust. Onaangekondigd wegvallen is
een incident. Die moet ze uit elkaar houden."

Een nette afsluiting schrijft een rustmarkering als laatste regel. Staat die er
bij het opstarten niet, dan is het een incident — en dat is een gekend feit in
plaats van een gat.
"""

import json
import os
import time

REGELSOORTEN_EINDE = {"rust"}

# Regels die het opschonen overleven, hoe oud ze ook zijn.
#
# Het opschonen is er voor hérstel: wat in de momentopname zit hoeft niet meer
# in het logboek. Maar metingen zijn geen herstelgegevens — dat zijn precies de
# "uitkomsten die je niet opnieuw wilt hoeven verdienen" waar N het over heeft.
# Op 8 aug 2026 stonden ze in hetzelfde bestand en at het opschonen ze op: na
# een run van 1500 stappen was er van de voortgang nog één regel over.
BLIJVEND = {"meting", "proefwerk", "wereld_dieper", "besluit"}


class Logboek:
    """Een logboek dat alleen aangevuld wordt. Nooit herschreven."""

    def __init__(self, pad, fsync_tussenpoos=1.0):
        self.pad = os.path.abspath(pad)
        self.fsync_tussenpoos = fsync_tussenpoos
        os.makedirs(os.path.dirname(self.pad), exist_ok=True)
        self._f = open(self.pad, "a", buffering=1)
        self._laatste_fsync = 0.0
        self._volgnummer = self._laatste_volgnummer()

    def _laatste_volgnummer(self):
        try:
            regels, _ = lees(self.pad)
        except FileNotFoundError:
            return 0
        return regels[-1]["nr"] if regels else 0

    def schrijf(self, soort, **velden):
        """Voeg een gebeurtenis toe.

        `soort` is de aard van de gebeurtenis, bijvoorbeeld "stap",
        "waarneming" of "meting". De rest is vrij.
        """
        self._volgnummer += 1
        regel = {
            "nr": self._volgnummer,
            "tijd": time.time(),
            "soort": soort,
            **velden,
        }
        self._f.write(json.dumps(regel, ensure_ascii=False) + "\n")

        nu = time.monotonic()
        if nu - self._laatste_fsync >= self.fsync_tussenpoos:
            self._naar_schijf()
            self._laatste_fsync = nu
        return self._volgnummer

    def _naar_schijf(self):
        self._f.flush()
        os.fsync(self._f.fileno())

    def rust(self, **velden):
        """Nette afsluiting. Zonder deze markering geldt het als incident."""
        self.schrijf("rust", **velden)
        self._naar_schijf()

    def schoon_op(self, tot_stap):
        """Kort het logboek in nadat er een momentopname is weggeschreven.

        Alleen aanroepen ná een geslaagde opname: regels van vóór `tot_stap`
        zitten daar al in.

        Dit is bewust een methode en geen losse functie. Het inkorten wisselt
        het bestand atomair om, en een `Logboek` dat het oude bestand nog open
        heeft, schrijft daarna in een inode die niet meer aan een naam hangt —
        het logboek lijkt dan te werken en is leeg. Alleen het logboek zelf kan
        die omwisseling veilig doen, want alleen het logboek kan zijn eigen
        bestand daarna heropenen.
        """
        self._naar_schijf()
        self._f.close()

        regels, _ = lees(self.pad)
        # >= en niet >: stap `tot_stap` zelf is nog niet uitgevoerd op het
        # moment van de opname. Zie "De telling" bovenaan.
        # En regels uit BLIJVEND gaan er nooit uit: die zijn geen
        # herstelgegevens maar het verslag zelf.
        houden = [r for r in regels
                  if r.get("soort") in BLIJVEND
                  or r.get("stap") is None or r["stap"] >= tot_stap]

        tijdelijk = self.pad + ".deel"
        with open(tijdelijk, "w") as f:
            for r in houden:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tijdelijk, self.pad)

        map_ = os.path.dirname(self.pad)
        fd = os.open(map_, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

        self._f = open(self.pad, "a", buffering=1)
        self._laatste_fsync = 0.0
        return len(regels) - len(houden)

    def sluit(self):
        if not self._f.closed:
            self._naar_schijf()
            self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.sluit()


def lees(pad):
    """Lees een logboek. Geeft (regels, soort_stilte) terug.

    Een afgekapte laatste regel wordt weggelaten in plaats van dat het lezen
    stukloopt. Dat is precies de vorm van beschadiging die je krijgt als de
    stroom wegvalt tijdens het schrijven, en dan wil je de regels dáárvoor nog
    steeds hebben.
    """
    regels = []
    with open(pad) as f:
        ruw = f.read().splitlines()

    for i, regel in enumerate(ruw):
        try:
            regels.append(json.loads(regel))
        except json.JSONDecodeError:
            if i == len(ruw) - 1:
                break          # afgekapte staart: verwacht, laatste regel valt af
            raise ValueError(
                f"logboek {pad} is beschadigd op regel {i + 1} — "
                f"niet de laatste, dus dit is geen afgekapte staart"
            )

    stilte = "rust" if regels and regels[-1]["soort"] in REGELSOORTEN_EINDE else "incident"
    return regels, stilte


def hervat(map_, tot_stap=None):
    """Alles wat je bij het opstarten moet weten.

    Geeft terug: welke gebeurtenissen er ná de momentopname zijn, of het
    afsluiten netjes ging, en hoe lang de stilte duurde. Wat er met die
    gebeurtenissen moet gebeuren beslist de aanroeper — dit weet niets van
    leren af.

    `tot_stap` is het stapnummer uit de momentopname. Regels van vóór dat punt
    zitten al in de opname en worden overgeslagen. Daardoor maakt het niet uit
    of het misging tussen het schrijven van de opname en het opschonen van het
    logboek: dubbel afspelen kan niet.
    """
    pad = os.path.join(map_, "logboek.jsonl")
    if not os.path.exists(pad):
        return {"gebeurtenissen": [], "stilte": "leeg", "gat_seconden": None,
                "laatste_tijd": None}

    regels, stilte = lees(pad)
    if tot_stap is not None:
        # >= en niet >: zie "De telling" bovenaan. De opname staat vóór stap
        # `tot_stap`, dus die stap moet nog wél afgespeeld worden.
        regels = [r for r in regels
                  if r.get("stap") is None or r["stap"] >= tot_stap]

    laatste = None
    gat = None
    if regels or stilte != "leeg":
        alles, _ = lees(pad)
        if alles:
            laatste = alles[-1]["tijd"]
            gat = time.time() - laatste

    return {
        "gebeurtenissen": regels,
        "stilte": stilte,          # "rust" = aangekondigd, "incident" = weggevallen
        "gat_seconden": gat,       # tijd als expliciete grootheid, geen ontbrekende data
        "laatste_tijd": laatste,
    }


# Let op: er is bewust géén losse schoon_op(map, tot_stap) meer.
# Zie Logboek.schoon_op — het inkorten wisselt het bestand atomair om, en een
# Logboek dat het oude bestand nog open heeft schrijft daarna in een inode
# zonder naam. Het logboek lijkt dan te werken en blijft leeg. Die fout is op
# 8 aug 2026 door de toets gevangen; laat dit niet terugkomen als losse functie.
