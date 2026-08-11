"""
Nieuwsgierigheid — waar werkt ze aan?

Fase 6 zegt het expliciet: *"S zit er in ruwe vorm al eerder in, en dat is met
opzet. Fase 1 zegt dat eigen initiatief de maatstaf is en dat wat ze zonder
opdracht oppakt het signaal is — dan moet er vanaf dag één iets zijn dat die
keuze stuurt, al is het maar nieuwsgierigheid die uitdooft bij bekend
materiaal."*

Dit is die ruwe vorm. Eén signaal, twee delen:

  **onkunde** — waar ze slecht scoort is meer te halen. Dooft vanzelf uit
  zodra ze het kan, en dat is precies wat "nieuwsgierigheid die uitdooft"
  betekent.

  **vervlogen tijd** — wat lang niet langs is geweest wordt weer aantrekkelijk.
  Zonder dit blijft ze hangen bij het moeilijkste en ziet ze de rest nooit meer
  terug, en dan meet C iets dat de keuze zelf veroorzaakt heeft in plaats van
  vergeten.

Beide zijn nodig. Alleen onkunde levert een fixatie op; alleen tijd levert een
rondje langs de velden op dat net zo goed willekeurig had kunnen zijn.

HET MOET HERHAALBAAR ZIJN
-------------------------
De keuze wordt getrokken met een trekker die uit `(zaad, stapnummer)` volgt.
Dezelfde run geeft dus dezelfde volgorde van onderwerpen — anders is de
leerstroom niet herhaalbaar en is het meetpunt van fase 1 onhaalbaar.
"""

import taken


class Nieuwsgierigheid:
    def __init__(self, families=None, graden=None, uitdoving=6.0, bodem=0.05):
        self.soorten = [(f, g)
                        for f in (families or taken.FAMILIES)
                        for g in (graden or taken.GRADEN)]
        self.uitdoving = uitdoving      # hoe scherp onkunde de keuze stuurt
        self.bodem = bodem              # niets zakt ooit helemaal naar nul
        self.score = {s: 0.0 for s in self.soorten}
        self.laatst = {s: 0 for s in self.soorten}

    def voeg_toe(self, soort, stap=0):
        """Een onderwerp erbij dat er nog niet was.

        Nodig zodra de wereld dieper open gaat: er komt dan een moeilijkheid bij
        die nog niet bestond. Een nieuw onderwerp begint op score nul en is dus
        meteen aantrekkelijk — precies de bedoeling.
        """
        if soort in self.score:
            return False
        self.soorten.append(soort)
        self.score[soort] = 0.0
        self.laatst[soort] = stap
        return True

    def bijgewerkt(self, soort, score, stap):
        """Meld hoe goed ze het op dit onderwerp doet."""
        if soort not in self.score:
            self.voeg_toe(soort, stap)
        self.score[soort] = score
        self.laatst[soort] = stap

    def aantrekking(self, stap):
        """Hoe aantrekkelijk elk onderwerp nu is."""
        uit = {}
        for soort in self.soorten:
            onkunde = (1.0 - self.score[soort]) ** 2
            vervlogen = min(1.0, (stap - self.laatst[soort]) / 500.0)
            uit[soort] = self.bodem + onkunde + 0.5 * vervlogen
        return uit

    def kies(self, stap, trekker):
        """Kies een onderwerp. Naar verhouding, niet het hoogste.

        Het hoogste kiezen zou haar op één onderwerp vastzetten tot ze het kan,
        en dan is elke C-meting een meting van die volgorde en niet van
        vergeten.
        """
        gewichten = self.aantrekking(stap)
        totaal = sum(gewichten.values())
        # De trekker levert gehele getallen; daarmee wordt naar verhouding
        # getrokken zonder dat er drijvende komma's aan te pas komen — en dus
        # zonder dat de keuze per machine kan verschillen.
        punt = trekker.geheel(0, 1_000_000) / 1_000_000 * totaal
        loper = 0.0
        for soort, gewicht in gewichten.items():
            loper += gewicht
            if punt <= loper:
                return soort
        return self.soorten[-1]

    def stand(self):
        return {f"{f}/{g}": round(self.score[(f, g)], 3)
                for f, g in self.soorten}

    # --- mee in de momentopname -------------------------------------------

    def neem_mee(self):
        """Ook `laatst` gaat mee, niet alleen de scores.

        Zonder `laatst` denkt ze na een herstart dat ze alles net nog gezien
        heeft, en trekt vervlogen tijd nergens meer aan tot de klok opnieuw is
        opgebouwd — een subtiel andere Amber dan vóór de herstart.
        """
        return {"soorten": [list(s) for s in self.soorten],
                "score": {f"{f}/{g}": self.score[(f, g)] for f, g in self.soorten},
                "laatst": {f"{f}/{g}": self.laatst[(f, g)] for f, g in self.soorten}}

    def zet_terug(self, meegenomen):
        self.soorten = [tuple(s) for s in meegenomen["soorten"]]
        self.score, self.laatst = {}, {}
        for sleutel, waarde in meegenomen["score"].items():
            f, g = sleutel.rsplit("/", 1)
            self.score[(f, int(g))] = waarde
        for sleutel, waarde in meegenomen["laatst"].items():
            f, g = sleutel.rsplit("/", 1)
            self.laatst[(f, int(g))] = waarde
