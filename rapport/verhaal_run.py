"""
Het verhaal bij het eindverslag van run 5 — de duiding rond de cijfers.

maak-eindverslag.py leest dit bestand. De getallen in de tekst hieronder
zijn ná de finish met de hand tegen het log en de nameting gehouden; wie
ze wil narekenen kijkt in de tabellen ernaast, die rechtstreeks uit de
bestanden komen.

Geschreven in de nacht van 16 aug 2026, na de finish van run 5.
"""

VERHAAL = {
    "datum_finish": "16 aug 2026",
    "tabel_stap": 2500,
    "voorbeelden_per_vakje": 3,

    # de nameting van run 4 (14 aug 2026, DL380), voor het verschil per vakje
    "nameting_vorig": {
        ("rekenen", 1): 100, ("rekenen", 2): 96, ("rekenen", 3): 65, ("rekenen", 4): 81, ("rekenen", 5): 100,
        ("code", 1): 99, ("code", 2): 97, ("code", 3): 62, ("code", 4): 99, ("code", 5): 63,
        ("puzzel", 1): 99, ("puzzel", 2): 97, ("puzzel", 3): 99, ("puzzel", 4): 99, ("puzzel", 5): 100,
    },

    # uitleg per vakje uit de foutanalyse — wordt na de finish ingevuld
    "fouten_uitleg": {
        ("rekenen", 4): (
            "27 van de 28 missers zitten in de vermenigvuldiging, niet in het optellen of aftrekken erna (de 28e telt de <code>+ 61</code> "
            "twee keer). De vorm van dit vakje is <code>a * b ± c</code> en de uitwerking vraagt het product in één klap: "
            "<code>21 * 17 = 357 ; 357 - 75 = 282</code>. Bij 20 van de 28 gokt ze dat product en zit ze ernaast — de tweede factor "
            "is er telkens een tiener (13–19), en vaak lijkt het alsof de tientallen daarvan wegvallen: <code>2 * 19 = 18</code>, "
            "<code>3 * 17 = 21</code>, <code>8 * 15 = 80</code>, <code>17 * 19 = 203</code> — hetzelfde weglaten van het tiental dat "
            "de foutanalyse van run 4 bij rekenen 3 zag. Bij de andere 7 begint ze de "
            "tientallen-uitwerking die ze in deze run leerde voor de kale keersom (<code>21 * 10 = 210</code>) en springt dan meteen "
            "door naar de <code>± c</code>-stap — de eenheden vergeet ze. De keersom-splits van 14 aug heeft rekenen 3 van 65 naar 99% "
            "gebracht, maar geldt alleen voor de kále keersom; binnen een samengestelde som mag ze niet uitwerken en dan gokt ze "
            "weer, precies zoals in run 4 bij rekenen 3. Dat is een aanwijzing voor de wereld van run 6, ter overweging: laat de "
            "splits ook binnen <code>a * b ± c</code> gebeuren (<code>21 * 10 = 210 ; 21 * 7 = 147 ; 210 + 147 = 357 ; 357 - 75 = 282</code>) "
            "— nakijken leest het laatste getal, dus het bevroren blad blijft geldig. Dezelfde les als op 8 aug: ze moet mogen uitwerken."
        ),
        ("puzzel", 4): (
            "Alle 12 missers zijn hetzelfde: een rij waarvan het verschil zelf oploopt (57, 59, 70, 90, 119: verschillen 2, 11, 20, 29, "
            "telkens +9, dus 157) pakt ze aan met de methode van graad 5, <i>som van de vorige twee</i>: <code>57 + 59 = 116 ; "
            "59 + 116 = 175 ; …</code> — een uitwerking die netjes doorloopt maar bij het derde getal al niet meer klopt (116 is geen 70). "
            "Ze rekent goed, ze kiest de verkeerde steen. In run 4 stond dit vakje op 99% en graad 5 (som van de vorige twee) staat nu "
            "op 100%: de graad-5-methode is sterker geworden en duwt op de graad-4-rijen. Wat er in deze run veranderde is dat de "
            "puzzelwereld openging tot 9 en dat zij daar zelf het meest naartoe trok (puzzel 7, 9 en 8 waren haar drie vaakst gekozen "
            "onderwerpen, en puzzel 4 stond op vijf) — de hypothese is dus dat de nieuwe diepe puzzelstof de keuze van de methode "
            "verstoort, niet het rekenen. Een hypothese, geen meting: gemengd zou dit moeten laten zien en staat op 94."
        ),
        ("code", 5): (
            "Alle 9 missers zijn de som van twaalf tot vijftien termen (<code>for i in range(1, 16): totaal += f(i)</code>). De termenrij "
            "klopt telkens (<code>daarna steeds +14: 19 33 47 …</code>); de fout zit in de lopende som — en bij 7 van de 9 in de "
            "állerlaatste optelling, meestal één of twee tientallen ernaast: <code>1540 + 215</code> wordt 1775 in plaats van 1755, "
            "<code>581 + 79</code> wordt 670, <code>490 + 65</code> wordt 565. De twee andere struikelen eerder in de keten. Vergelijk "
            "run 4: toen braken alle 37 missers halverwege af omdat de schrijfruimte kleiner was dan de uitwerking. Dat plafond is weg "
            "(compacte vorm, schrijfruimte herijkt); wat overblijft is een rekenfout diep in een lange keten — 9 op de 100, geen muur."
        ),
    },

    "secties": {
        "samenvatting": """
<p>Run 5 was een korte run met nieuwe stof: 50.000 stappen (30 uur op de Z490), venster 768 → 1024, drie
reparaties in de wereld gericht op de vakjes die in run 4 stilstonden, en de gespreksjas met een eigen meetlat.
De run is netjes uitgedraaid: één proces van begin tot eind, nul herstarts na de eerste stap, tempo kaarsrecht op 2,2 s per stap.</p>
<p><b>De brede meters gingen omhoog en de nieuwe stof is geleerd.</b> Grondslag 87% → 94%, gemengd 87% → 92%
(gemiddelde van de laatste tien metingen), en het gesprek-blad van 7% naar 97–98% — de jas zat er binnen 500 stappen aan.
Ladder (89%) en diepte2 (~80%) bleven vlak, maar die twee zitten op hun plafond van 91 en 81: wat er op die bladen nog
mist is niet uitlegbaar (zie <i>Naast de run gemeten</i>). Het diepte-blad bleef op ~37% — al sinds run 3, en om dezelfde reden.</p>
<p>De wereld ging in de eerste 5.400 stappen open tot alle drie de hekken: rekenen 26 → 38, code 11 → 15, puzzel 6 → 9. Daarna was
er niets meer om open te maken. De nameting per vakje bevestigt dat de drie reparaties raak waren: <b>rekenen 3 van 65% naar 99%, code 3 van 62% naar 100%, code 5 van 63% naar 91%</b> — de drie meetpunten van deze run. Er zijn ook twee vakjes gezakt: rekenen 4 (81 → 72%) en puzzel 4 (99 → 88%); zie <i>Waar de fouten zitten</i>.</p>
<p class="zorg">Het aandachtspunt: <b>ze zit tegen het plafond van haar wereld aan, niet tegen dat van haar kunnen.</b>
De hekken zijn de gemeten grenzen van het venster (rekenen) en van de grammatica (code, puzzel); binnen die grenzen haalt
ze op de nieuwe diepte3-meetlat al 95%. Groei zit de komende run in de wereld (code stapelt tot 24, de keer-plus-steen) en in
het venster (1536) — en Cley heeft er 8 → 12 lagen bij gekozen. Dat is run 6. Het groei-advies (E) komt aan het eind van de run zelf op hetzelfde uit: vlak, wereld dicht, en diepte2 een tik onder zijn plafond → "overweeg een laag" (zie onderaan).</p>
""",

        "verbeteringen": """
<ul>
<li><b>Het gesprek: 7% → 97–98%.</b> Op stap 320.500 stond het al op 83%, op 321.000 op 90%. De jas is dun — eerst vertalen
naar de kale som, dan rekenen — en het rekenen kon ze al; het vertalen leerde ze in een paar honderd stappen. Op 13 aug las ze
"Wat is 3 plus 4?" nog als lijstfilter-taal.</li>
<li><b>Grondslag 87% → 94%, gemengd 87% → 92%.</b> Anders dan in run 4 kwam de winst hier niet in één sprong bij
de start maar in twee stappen: rond 335.000–345.000 (grondslag naar 92–95) en nog een tik na 360.000. In de nameting: <b>rekenen 3: 65 → 99%</b> (twee runs lang precies 65 — de kale keersom die ze in één klap gokte; met de tientallen-uitwerking is hij weg), <b>code 3: 62 → 100%</b> en <b>code 5: 63 → 91%</b> (de lange lussen die halverwege afbraken schrijft ze nu in de compacte vorm helemaal uit — wat overblijft is een optelfout in de staart).</li>
<li><b>Ladder en diepte2 hielden stand</b> (89 en ~80) terwijl het venster groeide en er nieuwe stof bij kwam — geen vergeten door de verbouwing.</li>
<li><b>Alle drie de hekken binnen 5.400 stappen open:</b> rekenen 38 op stap 321.740, code 15 op 320.368, puzzel 9 op 325.372. Rekenen
opende twaalf diepten in 1.740 stappen. Op de nieuwe diepte3-meetlat (uit de wereld van nu, tot rekenen 30) haalt ze rekenen 91–100% en code 97–100%.</li>
<li><b>Nul crashes, tempo stabiel</b> (2,10–2,28 s per blok van 2000 stappen), en de startfout van 14 aug was in twee minuten gedicht.</li>
</ul>
""",

        "fouten": """
<p>De nameting wijst drie zwakste vakjes aan — rekenen 4 (72%), puzzel 4 (88%), code 5 (91%) — en de foutanalyse
laat het eindbrein alle missers uitschrijven. Alle 49 missers zijn gelezen; het beeld per vakje staat hieronder, met de
eerste drie voluit (uitklappen). Daarnaast de bladen die om een andere reden vlak staan.</p>
<ul>
<li><b>Het diepte-blad bleef op 35–37%</b>, zoals in run 3 en 4. De stof op diepte 6 en 9 stamt van vóór de rijlengte-regel van
13 aug en toont zes getallen waar het patroon niet uit te halen is — hetzelfde geldt voor diepte2 (puzzel 6 en 9) en ladder
(puzzel 5 en 6), die daarmee op hun plafond van 81 en 91 zitten. Geen leerprobleem; een volle meter. De nieuwe bladen diepte3
en stapel nemen die rol over.</li>
<li><b>Twee vakjes zakten: rekenen 4 (81 → 72%) en puzzel 4 (99 → 88%).</b> Bij allebei is het één patroon dat alle missers
verklaart — zie hieronder. Rekenen 4 stond bij de tussenmeting op stap 351.000 al op 76%: het zakte aan het begin van de run en
bleef daar. Kleine verschuivingen als code 2 (97 → 95) en puzzel 2 (97 → 93) vallen binnen wat honderd opgaven aan ruis geven.</li>
<li><b>Het gemengd-blad (94%) blijft iets onder grondslag (95%)</b> — het verschil is klein, maar gemengd toetst ook of ze
ziet wélke soort ze voor zich heeft, en de puzzel-4-missers zijn precies dat soort fout.</li>
</ul>
<p class="stil">Bij de opgaven hieronder staat geen nummer: de bevroren bladen dragen hun opgaven zelf, niet een recept.</p>
""",
        "opzet": """
<ul>
<li><b>Een korte run: 50.000 stappen</b> (320.000 → 370.000), Cleys voorstel na run 4 —
daar zat de winst in de eerste ~35.000 stappen, dus: kortere runs, vaker bijsturen op een rungrens.</li>
<li><b>Venster 768 → 1024</b>, als groeistap op de rungrens: het groeicheckpoint is bit voor bit
bewezen (run5-start.pt, stap 320.000). Hekken op de gemeten grenzen van 1024: rekenen 38, code 15, puzzel 9.</li>
<li><b>Drie reparaties in de wereld</b>, uit de foutanalyse van run 4 (14 aug):
de <i>keersom-splits</i> (een vijfde van rekenen diepte 3–8 wordt een kale keersom met
tientallen-uitwerking, <code>87 * 10 = 870 ; 87 * 7 = 609 ; 870 + 609 = 1479</code> — de vorm die
twee runs op 65% stond bestond niet in haar leerstof), <i>lange lussen compact</i> (een kwart van code
diepte 5+ in het proefwerkformaat van 12–20 rondes met rijen-uitwerking, ~200 tekens in plaats van
~660) en de <i>schrijfruimte van code herijkt</i> (200·graad − 200; de oude grens lag onder haar eigen stof).</li>
<li><b>De gespreksjas</b> — de eerste stof die geen som is — met een eigen bevroren proefwerk
<i>gesprek</i>. Startstreep vóór de run: 1% (13 aug) en 7% op de eerste meting van deze run.</li>
<li>Bij de start het geheugen in: <b>één les van Cley</b> en <b>negen waarnemingen</b> uit de brievenbus (ritfoto's van het oog).</li>
<li>Verder ongewijzigd: 8 lagen, breedte 384, 14,4 M parameters · herhaling 37,5% · partij 64 ·
proefwerk elke 500 stappen, 150 opgaven per blad · determinisme aan · Z490 met de RTX 3070 Ti.</li>
<li>Meetpunten die vooraf zijn afgesproken: code 3 en 5, rekenen 3, het diepte-proefwerk, en de gesprek-startstreep.</li>
</ul>
""",

        "naast": """
<p class="stil">Terwijl de run op de Z490 liep, is er op de DL380 (15–16 aug) tegen kopieën van de
momentopname gemeten — lezen en meten, niets veranderde aan haar. De uitkomsten horen bij het beeld van deze run.</p>
<ul>
<li><b>diepte2 en ladder zijn vol.</b> diepte2: alles ~100% behalve puzzel 6 (21%) en 9 (3%) — van die
rijen is met de huidige grammatica maar 8 van 33 en 2 van 33 uitlegbaar (het blad toont zes getallen waar het
patroon niet uit te halen is); zij haalt 7 en 1. Plafond 81%, ze staat op 81. ladder: puzzel 5 en 6 met 4 en 3
van 20 uitlegbaar; zij haalt 4 en 3. Plafond 91%, ze staat op 89. <b>Een volle meter meet niets meer</b> —
vlak op deze twee bladen is géén leerprobleem. Beide zijn bevroren vóór de rijlengte-regel van 13 aug, dezelfde
ziekte als het diepte-blad.</li>
<li><b>Twee nieuwe bevroren proefwerken</b> (Cleys akkoord, alleen op de DL380 tot de rungrens):
<i>diepte3</i> — 495 opgaven uit de wereld van nu, rekenen tot 30, code tot 15, puzzel tot 9, alles past op 1024,
alleen oplosbare rijen. <b>Startstreep op stap 351.000: 95%</b> (code 97–100% t/m 15, rekenen 91–100% t/m 30,
puzzel 9: 55%). Ze zit voor code en puzzel tegen het plafond van de <i>wereld</i>: groeiruimte zit in de wereld,
niet in het proefwerk. En <i>stapel</i> — 297 opgaven: code 16/18/20/22/24 (gestapelde lussen en defs, nieuwe stof)
en puzzel 2/4/6/8 met alleen de nieuwe keer-plus-steen. Startstreep stap 351.000: <b>code 0%</b> (bestond nog niet
in haar wereld), <b>keer-plus 82/76/82/55%</b> — een nieuwe steen, en haar oude methode draagt over.</li>
<li><b>Hekmeting: het venster helpt alléén rekenen</b> — 38 op 1024, 60 op 1536, 82 op 2048. Code paste overal
maar de grammatica plafonneerde rond 15 (nu stapelt code vanaf diepte 16, tot 24); bij puzzel is de uitlegbaarheid
de muur (5–7% bruikbaar vanaf diepte 11), niet de lengte. Voor code en puzzel is de weg wereldbouw, geen venster.</li>
<li><b>De C-meting op het rijpe brein</b> (stap 351.000, 30.000 herinneringen, 1000 stappen alléén puzzels):
98% behouden mét herhaling en 99/98% zónder. Op het lege netwerk van 8 aug was dat 71% tegen 10%. Het rijpe brein
vergeet in zo'n kort blok vrijwel niets — deze meting scheidt de twee instellingen niet. Geen reden om herhaling
af te zetten: kort blok, één zaad. Een langere meting (5000 stappen) is 's nachts afgeblazen: zou hetzelfde tonen.</li>
<li><b>Het tempo van deze run, uitgezocht:</b> niets werd trager — 2,10 · 2,28 · 2,28 · 2,22 … 2,19 s per stap per
2000 stappen, kaarsrecht. Stap zonder poging 1,55 s, mét poging (zelf antwoorden, dan leren) 3,90 s, één op vier is een
poging. Duurder dan run 4 (1,42 s) door venster 1024: langere stof en ruimere schrijfruimte, plus de lange lussen die
bewust ~750 tekens schrijven. Er is geen CPU-kloof (2–5%). Een groter venster kost daarna niets meer: 1536 en 2048
draaien 0,91× en 0,90× de staptijd van 1024 — de rem is de schrijflengte van de pogingen, niet de aandacht.</li>
<li><b>Voor de P100's gemeten</b> (run-6-vorm, stille stand): 9,5 s per stap op één kaart, 7,05 met twee
(DataParallel), ~2× trager dan de 3070 Ti. Hefbomen: vol vermogen ×1,7 (Cleys oren), DDP (op de lijst), slankere
aandacht (softmax + maskers zijn ~33% van een stap). fp16 versnelt daar niet.</li>
<li><b>Gebouwd voor run 6, alle toetsen groen (14 toetsen, 260):</b> laaggroei op de rungrens (<code>--lagen</code>,
optimizer gaat mee, bit voor bit gecontroleerd), breedtegroei in de kern (koppen en feedforward-eenheden achter
nul-kolommen — nog niet aan de rungrens), activatie-checkpointing (VRAM-piek 4682 → 1295 MB, leerstap +35% tijd),
een vaste KV-cache bij het antwoorden (35% sneller, piek 7,3 → 4,4 GB), en de herhaalproef die op elke rungrens
bewijst dat de trainer bit voor bit herhaalt.</li>
</ul>
""",

        "bedrijf": """
<p>De acht startpogingen zijn de startfout van 14 aug 19:22–19:24: de les-koppeling las het paar
(regels, stilte) van <code>journal.read</code> als regels en viel om vóór de eerste stap; dezelfde avond gedicht,
daarna liep de run in één proces van begin tot eind — nul herstarts, nul verloren stappen. Tempo 2217 ms per stap
als lopend gemiddelde, per blok van 2000 stappen tussen 2,10 en 2,28 s. De dienst <code>amber-train</code> stopt
zelf na de laatste stap; <code>cijfers-bij-finish</code> (gebouwd 14 aug, dit was zijn eerste echte finish)
draaide daarna de nameting en de foutanalyse. De DL380 is om 01:10 uitgezet (Cley); na dit verslag volgen een
back-up en het uitzetten van de Z490 — de machine krijgt even rust, op Cleys wens.</p>
""",

        "nu": """
<p><b>De maat van run 6 is op 15 aug besloten (Cleys akkoord, bijgesteld 18:20):</b> venster 1536, hekken
rekenen 60 / code 24 / puzzel 10, herhaling 37,5%, doel 420.000 (opnieuw 50.000 stappen), en <b>8 → 12 lagen met
activatie-checkpointing aan</b> — Cleys keuze, na de kanttekening dat wereld en capaciteit dan tegelijk veranderen.
De nieuwe bladen diepte3 en stapel gaan op de rungrens mee, zodat de nieuwe stof (code 16–24, keer-plus) een meetlat heeft.</p>
<pre class="advies">rungrens.py --doel 420000 --venster 1536 --hek rekenen=60 --hek code=24 --hek puzzel=10 --lagen 12 --checkpointing</pre>
<p>Op de DL380, die kopieert alles naar de Z490 en bewijst onderweg de groeistap bit voor bit en de herhaalbaarheid
op de trainer. <b>Start alleen op Cleys woord.</b> Reken op een trager tempo: 12 lagen op 1536 met checkpointing is
op de 3070 Ti naar schatting 5–6 s per stap, dus 50.000 stappen is eerder drie dagen dan dertig uur — dat is een
schatting uit de tempometingen van 15–16 aug, geen meting van run 6 zelf.</p>
<p>Wat er na deze run open blijft staan (de prioriteitenlijst in <code>TE-DOEN.md</code>): DDP voor de twee P100's,
de aandacht slanker op Pascal, het bewijs dat de NAS netjes afsluit, en de breedtegroei aan de rungrens.</p>
""",
    },
}
