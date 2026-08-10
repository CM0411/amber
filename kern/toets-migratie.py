"""
Toetst de migratie — oud en nieuw moeten exact hetzelfde doen.

Elke vertaalde module krijgt hier zijn gelijkheids-toetsen: de Engelse
versie naast de Nederlandse, zelfde invoer, en het antwoord moet bit voor
bit gelijk zijn. Groeit mee met de migratie; als álles vertaald is en de
Nederlandse bestanden verdwijnen, vervalt dit bestand samen met hen.

De sleutelbrug (netwerk -> network) heeft zijn eigen toets:
toets-sleutelbrug.py, want die heeft het echte checkpoint nodig.

Draaien:  venv/bin/python kern/toets-migratie.py
"""

import determinisme                        # MOET vóór torch
determinisme.zet_vast(1234)

import sys

import determinism                         # mag ná determinisme: env staat al
import taken
import tekens
import tokens

geslaagd = 0
gefaald = 0


def toets(naam, goed, toelichting=""):
    global geslaagd, gefaald
    if goed:
        geslaagd += 1
        print(f"[  OK  ] {naam}")
    else:
        gefaald += 1
        print(f"[ FOUT ] {naam}")
    if toelichting:
        print(f"         {toelichting}")


print("=" * 70)
print("Toets — migratie (Nederlands en Engels doen exact hetzelfde)")
print("=" * 70)
print()

# --- tekens <-> tokens -----------------------------------------------------

print("--- tekens -> tokens ---")
toets("de vier eigen tekens en de omvang zijn dezelfde getallen",
      (tokens.QUESTION, tokens.ANSWER, tokens.END, tokens.PAD, tokens.VOCAB)
      == (tekens.VRAAG, tekens.ANTWOORD, tekens.EIND, tekens.VUL,
          tekens.OMVANG),
      "verschuiven die, dan wijst elke inbedding naar iets anders")

proeven = ["47 * 13", "Zet voort: 3, 6, 9, ?", "één röntgenfoto — ß≤ǿ",
           "a = 26\nb = 61\nprint(a - b)"]
toets("coderen is identiek op alles wat we haar voorleggen",
      all(tokens.encode(t) == tekens.codeer(t) for t in proeven))
toets("decoderen is identiek, ook met eigen tekens ertussen",
      all(tokens.decode([tekens.VRAAG] + tekens.codeer(t) + [tekens.EIND])
          == tekens.decodeer([tekens.VRAAG] + tekens.codeer(t) + [tekens.EIND])
          for t in proeven))

taak = taken.maak("rekenen", 3, 900)
r_nl, m_nl = tekens.taak_naar_reeks(taak)
r_en, m_en = tokens.task_to_sequence(taak)
toets("een taak wordt exact dezelfde reeks en hetzelfde masker",
      r_nl == r_en and m_nl == m_en)
toets("de vraagreeks en het teruglezen van een antwoord zijn gelijk",
      tekens.vraag_naar_reeks(taak) == tokens.question_to_sequence(taak)
      and tekens.antwoord_uit_reeks(r_nl) == tokens.answer_from_sequence(r_en))

b_nl = tekens.bundel([r_nl, r_nl[:9]], [m_nl, m_nl[:9]])
b_en = tokens.batch([r_en, r_en[:9]], [m_en, m_en[:9]])
toets("bundelen met opvulling is gelijk", b_nl == b_en)

# --- determinisme <-> determinism ------------------------------------------

print()
print("--- determinisme -> determinism ---")
toets("dezelfde zaad-afleiding, over een reeks stappen",
      all(determinisme.zaad_voor_stap(s, zaad=777)
          == determinism.seed_for_step(s, seed=777)
          for s in (0, 1, 2, 100, 170_000, 10**12)))

determinism.lock(1234)
toets("lock() zet en controleert dezelfde vlaggen",
      determinism.verify() and determinisme.controleer())
# De afleidingsbeschrijving is documentatie en heet in elke taal anders;
# het gedrág is hierboven al bewezen gelijk. Alleen het zaad moet kloppen.
toets("de stand meldt hetzelfde zaad",
      determinism.state()["seed"] == determinisme.stand()["zaad"])
toets("begin_step en begin_stap geven hetzelfde stapzaad",
      determinism.begin_step(41) == determinisme.begin_stap(41))

# --- nieuwsgierigheid <-> curiosity ----------------------------------------

print()
print("--- nieuwsgierigheid -> curiosity ---")
import curiosity
import nieuwsgierigheid

nl = nieuwsgierigheid.Nieuwsgierigheid()
en = curiosity.Curiosity()
zelfde = True
for stap in range(1, 400):
    t1 = taken.Trekker(determinisme.zaad_voor_stap(stap, zaad=55))
    t2 = taken.Trekker(determinisme.zaad_voor_stap(stap, zaad=55))
    k1 = nl.kies(stap, t1)
    k2 = en.pick(stap, t2)
    if k1 != k2:
        zelfde = False
        break
    score = (stap % 7) / 7
    nl.bijgewerkt(k1, score, stap)
    en.update(k2, score, stap)
toets("vierhonderd stappen lang exact dezelfde keuzes", zelfde,
      "zelfde trekkerstroom, zelfde scores, zelfde onderwerpkeuze")
toets("nieuwe onderwerpen komen er gelijk bij",
      nl.voeg_toe(("rekenen", 9), 400) == en.add(("rekenen", 9), 400)
      and nl.kies(401, taken.Trekker(1)) == en.pick(401, taken.Trekker(1)))

en2 = curiosity.Curiosity()
en2.restore(en.carry())
toets("meenemen en terugzetten geeft dezelfde vervolgkeuzes",
      en.pick(500, taken.Trekker(9)) == en2.pick(500, taken.Trekker(9)))

# --- taken <-> tasks ---------------------------------------------------------

print()
print("--- taken -> tasks ---")
import tasks

toets("families, graden, meetlatgrens en taakzaad zijn identiek",
      tasks.FAMILIES == taken.FAMILIES and tasks.GRADES == taken.GRADEN
      and tasks.TEST_UPTO == taken.TEST_TOT
      and tasks.TASK_SEED == taken.TAAK_ZAAD)

t1, t2 = taken.Trekker(4242), tasks.Picker(4242)
toets("Trekker en Picker geven dezelfde stroom",
      all(t1.geheel(0, 10**9) == t2.integer(0, 10**9) for _ in range(500)))

zelfde = True
for fam in tasks.FAMILIES:
    for gr in tasks.GRADES:
        for n in (0, 7, 199, 200, 5000, 81_733):
            a = taken.maak(fam, gr, n)
            b = tasks.make(fam, gr, n)
            if (a.opgave, a.oplossing) != (b.problem, b.solution):
                zelfde = False
toets("elke taak is bit voor bit dezelfde, alle families en graden", zelfde,
      "90 taken vergeleken over het hele bereik")

taak_nl = taken.maak("code", 5, 123)
taak_en = tasks.make("code", 5, 123)
toets("nakijken oordeelt identiek, ook via de Nederlandse aliassen",
      all(taak_nl.nakijk(a) == taak_en.check(a) == taak_en.nakijk(a)
          for a in (taak_nl.oplossing, "fout 12", "", "uitwerking = "
                    + taak_nl.oplossing))
      and taak_en.opgave == taak_nl.opgave
      and taak_en.te_leren() == taak_nl.te_leren())

toets("de leerreeks vindt exact dezelfde schone taken",
      [t.problem for t in tasks.learning_tasks("rekenen", 1, 60)]
      == [t.opgave for t in taken.leerreeks("rekenen", 1, 60)])
toets("de meetlat is exact dezelfde",
      [t.problem for t in tasks.benchmark("puzzel", 4)]
      == [t.opgave for t in taken.testverzameling("puzzel", 4)])
toets("besmetting wordt identiek herkend",
      all(tasks.is_contaminated(tasks.make("rekenen", 1, n))
          == taken.is_besmet(taken.maak("rekenen", 1, n))
          for n in range(200, 700)))

# --- wereld <-> world --------------------------------------------------------

print()
print("--- wereld -> world ---")
import wereld
import world

toets("zaad, hekken en tekstgrens zijn identiek",
      world.WORLD_SEED == wereld.WERELD_ZAAD
      and world.MAX_DEPTH == wereld.MEESTE_DIEPTE
      and world.MAX_DEPTH_PER == wereld.MEESTE_DIEPTE_PER
      and world.MAX_CHARS == wereld.MEESTE_TEKENS)

zelfde = True
geen_gelijk = True
for fam in world.FAMILIES:
    for d in (1, 2, 3, 5, world.max_depth(fam)):
        for n in range(4000, 4120):
            a = wereld.maak(fam, d, n)
            b = world.make(fam, d, n)
            if (a is None) != (b is None):
                geen_gelijk = False
            elif a is not None and (a.opgave, a.oplossing, a.uitwerking) \
                    != (b.problem, b.solution, b.working):
                zelfde = False
toets("elke wereldtaak is bit voor bit dezelfde, opgave én uitwerking",
      zelfde, "1800 taken over alle families en diepten, tot aan de hekken")
toets("onverklaarbare taken vallen aan beide kanten gelijk af", geen_gelijk)

slotje = {wereld.maak("rekenen", 3, 8000).opgave}
toets("de leerreeks kiest exact dezelfde schone, passende taken",
      [t.problem for t in world.learning_tasks("rekenen", 3, 50,
                                               start=8000, exclude=slotje)]
      == [t.opgave for t in wereld.leerreeks("rekenen", 3, 50,
                                             vanaf=8000, uitsluiten=slotje)])
toets("past en fits oordelen gelijk, ook bij een kleiner venster",
      all(world.fits(world.make("code", 8, n), 300)
          == wereld.past(wereld.maak("code", 8, n), 300)
          for n in range(1000, 1200) if wereld.maak("code", 8, n)))

# --- herhaalgeheugen <-> replay_memory ---------------------------------------

print()
print("--- herhaalgeheugen -> replay_memory ---")
import herhaalgeheugen
import replay_memory

fles_nl = herhaalgeheugen.Flessenhals(lengte=200)
fles_en = replay_memory.Bottleneck(length=200)
proef_taak = wereld.maak("rekenen", 4, 5000)
toets("de flessenhals codeert exact hetzelfde, sleutels incluis",
      fles_nl.codeer(proef_taak, "x", True)
      == fles_en.encode(proef_taak, "x", True))
toets("en ontcijfert exact hetzelfde",
      fles_nl.ontcijfer(fles_nl.codeer(proef_taak, None, None))
      == fles_en.decode(fles_en.encode(proef_taak, None, None)))

lang_taak = wereld.maak("rekenen", 12, 6000)
w_nl = w_en = None
try:
    herhaalgeheugen.Flessenhals(lengte=64).codeer(lang_taak, None, None)
except herhaalgeheugen.TePasseren:
    w_nl = True
try:
    replay_memory.Bottleneck(length=64).encode(lang_taak, None, None)
except replay_memory.Refused:
    w_en = True
toets("weigeren gebeurt aan beide kanten op dezelfde ervaring",
      w_nl is True and w_en is True)

g_nl = herhaalgeheugen.Herhaalgeheugen(ruimte=80,
                                       flessenhals=herhaalgeheugen.Flessenhals(lengte=512))
g_en = replay_memory.ReplayMemory(capacity=80,
                                  bottleneck=replay_memory.Bottleneck(length=512))
stroom = [wereld.maak(f, d, n)
          for f in ("rekenen", "puzzel") for d in (1, 2, 3)
          for n in range(3000, 3060)]
for taak in stroom:
    if taak is None:
        continue
    g_nl.onthoud(taak, None, None)
    g_en.remember(taak, None, None)
toets("volle voorraad met evenwichtig vergeten: exact dezelfde inhoud",
      g_nl.neem_mee() == g_en.carry(),
      f"{len(g_en)} herinneringen, zelfde volgorde en zelfde slachtoffers")

g_en2 = replay_memory.ReplayMemory()
g_en2.restore(g_nl.neem_mee())          # een Nederlands checkpoint erin
t1, t2 = taken.Trekker(31), taken.Trekker(31)
toets("een run-3-checkpoint laadt en herhaalt identiek",
      g_nl.herhaal(12, t1) == g_en2.replay(12, t2))
toets("de stand meldt dezelfde getallen", g_nl.stand() == g_en.status())

print()
print("=" * 70)
print(f"geslaagd: {geslaagd}    gefaald: {gefaald}")
print("=" * 70)
sys.exit(0 if gefaald == 0 else 1)
