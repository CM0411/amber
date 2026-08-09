"""
De leerkern — een transformer die kan groeien.

Met de hand geschreven en niet uit een bibliotheek getrokken, om de reden die
in de roadmap staat: *"een netwerk dat tijdens het draaien groeit kun je alleen
bouwen als je elke laag in handen hebt."*

DRIE KEUZES DIE VASTLIGGEN
--------------------------
**1. Groeien verandert de functie niet.** Elke residutak heeft een eigen
geleerde weegfactor die op nul begint:

    x = x + alfa * tak(norm(x))

Een nieuw blok invoegen met alfa = 0 laat de uitvoer **bit voor bit** gelijk.
Het blok leert zich daarna in. Zonder dit is groeien een sprong waarbij alles
wat ze kon in één klap verschuift, en dan meet je bij E geen groei maar schade.
Kost nu een paar regels, is achteraf een herbouw.

**2. Posities via draaiing (RoPE), niet via een geleerde positietabel.** Een
tabel legt het venster voorgoed vast: langer maken betekent nieuwe parameters
op plekken waar nooit iets geleerd is. Draaiing heeft geen parameters en rekt
mee. Het venster zal zeker groeien — bij fase 2 gaat ze praten — en dan wil je
niet je checkpoints hoeven weggooien.

**3. De aandacht is met de hand uitgeschreven**, niet via
`scaled_dot_product_attention`. Die kiest per aanroep een implementatie en de
achterwaartse stap is niet altijd deterministisch. Zelf uitschrijven kost wat
snelheid en levert een eis op die zwaarder weegt: herhaalbaarheid.

OVER OPVULLING
--------------
Opvulling staat achteraan en de aandacht is causaal, dus een echt teken kijkt
nooit naar opvulling die erna komt. Alleen opvulposities zien opvulling, en die
tellen niet mee in de fout. Er is dus geen apart masker voor nodig.
"""

import math

import torch
import torch.nn as nn
import torch.nn.functional as F

import tekens


def _draaihoeken(lengte, kopmaat, apparaat, vanaf=0):
    """De hoeken voor RoPE. In fp32 gerekend, ook als de rest fp16 is —
    hoeken zijn goedkoop en precisie hier scheelt merkbaar.

    `vanaf` schuift de plaatsen op. Bij het schrijven van een antwoord komt er
    één teken tegelijk bij, en dat hoort de hoek van zijn eigen plaats te
    krijgen en niet die van plaats nul.
    """
    stap = torch.arange(0, kopmaat, 2, device=apparaat, dtype=torch.float32)
    frequentie = 1.0 / (10000.0 ** (stap / kopmaat))
    plaats = torch.arange(vanaf, vanaf + lengte,
                          device=apparaat, dtype=torch.float32)
    hoek = torch.outer(plaats, frequentie)
    return torch.cos(hoek), torch.sin(hoek)


def _draai(x, cos, sin):
    """Draai elk paar getallen over de hoek die bij zijn plaats hoort.

    x is (partij, koppen, lengte, kopmaat).
    """
    even, oneven = x[..., 0::2], x[..., 1::2]
    cos = cos.to(x.dtype)[None, None, :, :]
    sin = sin.to(x.dtype)[None, None, :, :]
    return torch.stack((even * cos - oneven * sin,
                        even * sin + oneven * cos), dim=-1).flatten(-2)


class Aandacht(nn.Module):
    def __init__(self, breedte, koppen):
        super().__init__()
        if breedte % koppen:
            raise ValueError(f"breedte {breedte} niet deelbaar door {koppen} koppen")
        self.koppen = koppen
        self.kopmaat = breedte // koppen
        if self.kopmaat % 2:
            raise ValueError("kopmaat moet even zijn voor de draaiing")
        self.naar_qkv = nn.Linear(breedte, 3 * breedte, bias=False)
        self.uitgang = nn.Linear(breedte, breedte, bias=False)

    def forward(self, x, cos, sin, cache=None, sleutelmasker=None):
        """Geeft (uitvoer, nieuwe cache) terug.

        `cache` zijn de sleutels en waarden van alles wat er al stond. Bij het
        schrijven van een antwoord scheelt dat alles: zonder cache wordt bij
        elk teken de hele zin opnieuw door alle lagen gehaald, en bij achtenveertig
        tekens is dat achtenveertig keer hetzelfde werk.

        `sleutelmasker` markeert plaatsen waar niets echts staat. Bij het
        antwoorden wordt links opgevuld — anders eindigen de vragen op
        verschillende plaatsen en klopt de cache niet — en die opvulling mag
        nergens in meetellen.
        """
        partij, lengte, breedte = x.shape
        qkv = self.naar_qkv(x)
        q, k, v = qkv.chunk(3, dim=-1)
        vorm = (partij, lengte, self.koppen, self.kopmaat)
        q = q.view(vorm).transpose(1, 2)
        k = k.view(vorm).transpose(1, 2)
        v = v.view(vorm).transpose(1, 2)

        q = _draai(q, cos, sin)
        k = _draai(k, cos, sin)

        if cache is not None and cache[0] is not None:
            k = torch.cat((cache[0], k), dim=2)
            v = torch.cat((cache[1], v), dim=2)
        nieuwe_cache = (k, v)

        scores = (q @ k.transpose(-2, -1)) / math.sqrt(self.kopmaat)

        # Alleen een causaal verbod als vraag en sleutel even lang zijn — dat
        # is de volledige doorgang. Schrijft ze één teken tegen een gevulde
        # cache, dan mag dat teken alles zien wat ervóór staat.
        if q.shape[2] == k.shape[2]:
            verbod = torch.ones(lengte, lengte,
                                device=x.device, dtype=torch.bool).triu(1)
            scores = scores.masked_fill(verbod, float("-inf"))
        if sleutelmasker is not None:
            scores = scores.masked_fill(sleutelmasker[:, None, None, :], float("-inf"))

            # Een opvulpositie mag nergens naar kijken: alles staat dan op
            # min-oneindig, en de softmax daarvan is NaN. Die NaN kruipt via
            # de residustroom door de hele partij en maakt élk antwoord stuk,
            # ook dat van de taken die niets mankeren. Zulke rijen krijgen
            # daarom gelijke gewichten; hun uitvoer is onzin maar eindig, en
            # er wordt nooit uit gelezen.
            leeg = torch.isinf(scores).all(dim=-1, keepdim=True)
            scores = scores.masked_fill(leeg, 0.0)

        gewicht = torch.softmax(scores, dim=-1)
        uit = gewicht @ v
        uit = uit.transpose(1, 2).reshape(partij, lengte, breedte)
        return self.uitgang(uit), nieuwe_cache


class Voorwaarts(nn.Module):
    def __init__(self, breedte, factor=4):
        super().__init__()
        self.omhoog = nn.Linear(breedte, factor * breedte, bias=False)
        self.omlaag = nn.Linear(factor * breedte, breedte, bias=False)

    def forward(self, x):
        return self.omlaag(F.gelu(self.omhoog(x)))


class Blok(nn.Module):
    """Eén laag. Twee residutakken, elk met een eigen weegfactor.

    Beide factoren beginnen op nul: bij het invoegen doet dit blok niets en
    laat het de uitvoer exact ongemoeid.
    """

    def __init__(self, breedte, koppen):
        super().__init__()
        self.norm1 = nn.LayerNorm(breedte)
        self.aandacht = Aandacht(breedte, koppen)
        self.alfa1 = nn.Parameter(torch.zeros(1))

        self.norm2 = nn.LayerNorm(breedte)
        self.voorwaarts = Voorwaarts(breedte)
        self.alfa2 = nn.Parameter(torch.zeros(1))

    def forward(self, x, cos, sin, cache=None, sleutelmasker=None):
        uit, nieuwe_cache = self.aandacht(self.norm1(x), cos, sin,
                                          cache, sleutelmasker)
        x = x + self.alfa1 * uit
        x = x + self.alfa2 * self.voorwaarts(self.norm2(x))
        return x, nieuwe_cache


class Kern(nn.Module):
    def __init__(self, lagen=8, breedte=384, koppen=6, venster=512):
        super().__init__()
        self.breedte = breedte
        self.koppen = koppen
        self.venster = venster

        self.inbedding = nn.Embedding(tekens.OMVANG, breedte)
        self.blokken = nn.ModuleList(Blok(breedte, koppen) for _ in range(lagen))
        self.slotnorm = nn.LayerNorm(breedte)
        self.uitbedding = nn.Linear(breedte, tekens.OMVANG, bias=False)

        nn.init.normal_(self.inbedding.weight, std=0.02)
        nn.init.normal_(self.uitbedding.weight, std=0.02)

    def forward(self, codes):
        """codes is (partij, lengte). Geeft de scores per teken terug."""
        return self.vooruit(codes)[0]

    def vooruit(self, codes, cache=None, vanaf=0, sleutelmasker=None):
        """Geeft (scores, cache) terug.

        `vanaf` is de plaats waar deze tekens beginnen. Bij het schrijven van
        een antwoord staat er al iets in de cache, en dan hoort het nieuwe
        teken de draaihoek van zíjn plaats te krijgen — niet die van plaats nul.
        """
        partij, lengte = codes.shape
        if vanaf + lengte > self.venster:
            raise ValueError(
                f"plaats {vanaf + lengte} valt buiten venster {self.venster}")

        x = self.inbedding(codes)
        cos, sin = _draaihoeken(lengte, self.blokken[0].aandacht.kopmaat,
                                codes.device, vanaf)
        nieuw = []
        for i, blok in enumerate(self.blokken):
            x, blokcache = blok(x, cos, sin,
                                cache[i] if cache else None, sleutelmasker)
            nieuw.append(blokcache)
        return self.uitbedding(self.slotnorm(x)), nieuw

    # --- groeien ----------------------------------------------------------

    def voeg_blok_toe(self, positie=None):
        """Voeg een laag toe. De uitvoer verandert hierdoor niet.

        Het nieuwe blok heeft beide weegfactoren op nul en laat de residustroom
        dus exact door. Dat is geen benadering: `x + 0 * iets` is bit voor bit
        `x`. Het blok leert zich daarna in.

        Let op voor fase 5: de optimizer kent deze parameters nog niet. Wie
        laat groeien moet ook de optimizer bijwerken — zie de roadmap, "een
        netwerk dat groeit breekt de toestand van de optimizer".
        """
        positie = len(self.blokken) if positie is None else positie
        nieuw = Blok(self.breedte, self.koppen).to(self.inbedding.weight.device)
        blokken = list(self.blokken)
        blokken.insert(positie, nieuw)
        self.blokken = nn.ModuleList(blokken)
        return nieuw

    # --- boekhouding ------------------------------------------------------

    def aantal_parameters(self):
        return sum(p.numel() for p in self.parameters())

    def vorm(self):
        """Alles wat nodig is om dit netwerk opnieuw op te bouwen.

        Gaat mee in het checkpoint: zonder de vorm weet je bij het laden niet
        hoeveel lagen er waren, en na groei is dat elke keer anders.
        """
        return {
            "lagen": len(self.blokken),
            "breedte": self.breedte,
            "koppen": self.koppen,
            "venster": self.venster,
            "parameters": self.aantal_parameters(),
        }

    @staticmethod
    def uit_vorm(vorm):
        return Kern(lagen=vorm["lagen"], breedte=vorm["breedte"],
                    koppen=vorm["koppen"], venster=vorm["venster"])
