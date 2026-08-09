# Het tweede C-mechanisme

Plan: rekenen/1 → puzzel/1, 500 stappen per familie, partij 32, zaad 20260808.
Alle opstellingen doen evenveel stappen met een even grote partij.

```

opstelling           rekenen top  aan het eind  behouden  puzzel  nieuwe taken    tijd
---------------------------------------------------------------------------------------
geen bescherming            60%           8%       13%    19%        32,000     68s
herhaling 25%               58%          31%       53%    24%        24,000     68s
herhaling 50%               45%          40%       89%     6%        16,000     65s
rem, zwak (1e2)             60%           7%       12%    15%        32,000     74s
rem, midden (1e4)           60%           9%       15%     5%        32,000     73s
rem, sterk (1e6)            60%          21%       35%     1%        32,000     79s
```

## Uitkomst: de rem verliest op elke as

Bij zijn beste instelling (1e6) haalt de rem 35% behouden, maar dan is het leren
van puzzels ingestort naar 1%. Herhaling van 25% haalt 53% behouden **én** 24%
op puzzels — beter op allebei tegelijk, en sneller.

Kijk naar de reeks: bij oplopende remkracht zakken de puzzels van 15% naar 5%
naar 1%, terwijl behouden nauwelijks meebeweegt (12 → 15 → 35). **De rem remt
niet selectief maar bevriest het hele netwerk.** Dat is precies wat hij niet zou
moeten doen; het idee was dat hij alleen de belangrijke gewichten vasthoudt.

Hij is bovendien langzamer: 74–79 s tegen 65–68 s, door de strafterm over 14,4
miljoen gewichten bij elke stap plus het eenmalig vaststellen van het belang.

**Conclusie: herhaling blijft het mechanisme. De rem gaat niet mee.**

## Het onverwachte resultaat

**Herhaling van 25% verslaat "geen bescherming" op beide assen tegelijk:**
53% tegen 13% behouden, én 24% tegen 19% op puzzels — met een kwart mínder
nieuwe taken. Dat is geen afweging maar gewoon beter.

Bij 50% is er wél een steile prijs (puzzels 6%). Ergens tussen 25% en 50% ligt
dus een omslagpunt, en 25% lijkt aan de goede kant daarvan te liggen.

Waarom dit zo is, is niet gemeten. Aannemelijk is dat oud materiaal ertussen
voorkomt dat het netwerk in een smalle groef schiet, maar dat is een verklaring
achteraf.

## Wat deze meting niet draagt

**Dit is één zaad.** Het verschil tussen 12%, 13% en 15% is ruis en daar mag
niets uit gelezen worden. Het verschil tussen de rem en herhaling is groot
genoeg om op te vertrouwen. Maar **de keuze tussen 25% en 50% herhaling is
precies zo'n keuze waar één run te weinig voor is**, en het is wel de keuze die
hierna standaard gebruikt gaat worden. Die verdient meerdere zaden.

Verder: de remkracht is in stappen van honderd afgetast, het belang is op
veertig partijen geschat, en het model is klein terwijl de sprong tussen de
onderwerpen groot is. Geen van die drie verandert waarschijnlijk de richting,
maar ze verdienen vermelding.
