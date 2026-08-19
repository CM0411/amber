"""Het bevroren proefwerk antwoord — de twaalfde familie (19 aug 2026, Cley: terug kunnen praten).

Zij stelt een vraag (mag ik meer X oefenen? / mag ik dieper in X?), Cley
antwoordt — ja, nee, later, eerst X, of niets (zwijgen is nee) — en zij
zegt wat dat betekent; nagekeken als tekst.

    antwoord 1 … 12, 222 samen:
      graad  1- 3:  6 per graad   (de wereld telt hier maar 40 opgaven)
      graad  4- 6:  8 per graad   (80, waarvan 40 nieuw t.o.v. 1-3)
      graad  7- 9: 30 per graad   (260, waarvan 180 nieuw)
      graad 10-12: 30 per graad   (440, allemaal nieuw: twee beurten)

De voorraden nesten per blok van drie graden: alles wat graad 1-3 kan
maken, kan 4-6 ook maken, en 7-9 ook (binnen een blok zijn de voorraden
gelijk). Daarom hoort een opgave bij het LAAGSTE blok waar ze voorkomt —
een hoger blok toetst alleen wat daar nieuw is (later, geen antwoord,
eerst X, twee beurten). Zo blijft in elke laag leerstof over.

Nummers vanaf 1.500.000; het slot houdt de leerstof erbuiten. Geen opgave
komt in twee graden voor.

Waarom niet 30 per graad (eerste versie, 360, 19 aug 11:52) en ook niet
8/15/30/30 zonder blokregel (tweede, 249, 13:55): de nesting — drie keer
30 at de 40 lage opgaven op, en ook 8/15/30 deed dat nog via de graden
4-9. De trainer had dan niets meer om van te leren (learning_tasks: 0
vrij; test-world rood vóór de knip naar 7.2). Beide eerdere versies staan
in proefwerken-verlaten/; zij heeft er nooit op gezeten, dus er gaat geen
vergelijking verloren.

Draaien op de DL380 (moederkopie), één keer:
  venv/bin/python fase1/antwoord-proefwerk.py
"""
import sys
sys.path.insert(0, "/home/arch/amber-werk/kern")
import exams
import world

PER_GRAAD = {1: 6, 2: 6, 3: 6, 4: 8, 5: 8, 6: 8,
             7: 30, 8: 30, 9: 30, 10: 30, 11: 30, 12: 30}
BLOK = {d: (d - 1) // 3 for d in PER_GRAAD}        # 1-3 → 0, 4-6 → 1, …
START = 1_500_000
ROOM = 1536 - 112
VERKEN = 20_000          # nummers per graad om de voorraad te leren kennen

if exams.exists("antwoord"):
    sys.exit("proefwerk 'antwoord' bestaat al — een proefwerk wordt nooit "
             "overschreven; niets gedaan")

# de voorraad per blok, en wat al in een lager blok voorkomt
lager = {}
gezien = set()
for blok in sorted(set(BLOK.values())):
    graden = [d for d in PER_GRAAD if BLOK[d] == blok]
    for d in graden:
        lager[d] = set(gezien)
    nieuw = set()
    for d in graden:
        for n in range(START, START + VERKEN):
            t = world.make("antwoord", d, n)
            if t is not None:
                nieuw.add(t.problem)
    gezien |= nieuw

slot = exams.material()
gekozen = []
al = set()                      # opgaven die al in een andere graad zitten
for diepte, per_diepte in PER_GRAAD.items():
    n = START
    per, geprobeerd, te_lang, te_laag = [], 0, 0, 0
    while len(per) < per_diepte:
        if n > START + 200_000:
            sys.exit(f"antwoord {diepte}: nummerruimte op — stop")
        t = world.make("antwoord", diepte, n)
        n += 1
        geprobeerd += 1
        if t is None:
            continue
        if not world.fits(t, ROOM):
            te_lang += 1
            continue
        if t.problem in lager[diepte]:
            te_laag += 1            # hoort bij een lager blok
            continue
        if t.problem in slot or t.problem in al:
            continue
        # Nakijken moet op de eigen uitwerking uitkomen — anders is het
        # geen eerlijke opgave maar een fout in de grammatica.
        if not t.check(t.working or t.solution):
            sys.exit(f"antwoord {diepte} nummer {n - 1}: uitwerking komt niet "
                     f"op de oplossing uit — stop")
        per.append(t)
        al.add(t.problem)
    langste = max(len(t.problem) + len(t.to_learn()) for t in per)
    gekozen += per
    print(f"  antwoord diepte {diepte:>2}: {len(per)} opgaven uit {geprobeerd} "
          f"nummers ({te_lang} te lang, {te_laag} van een lager blok), "
          f"langste {langste} tekens")

aantal = exams.freeze(
    "antwoord",
    "De twaalfde familie (19 aug 2026): zij leert wat Cleys antwoord op haar "
    "vraag betekent — ja, nee, later, eerst X, en geen antwoord = ik wacht "
    "(zwijgen is nee). Graad 10-12: twee beurten, het laatste geldt. "
    "Nagekeken als tekst. Diepte 1 t/m 12; 6 per graad bij 1-3, 8 bij 4-6, "
    "30 bij 7-12 (222 samen). Een opgave hoort bij het laagste blok "
    "(1-3, 4-6, 7-9, 10-12) waar ze voorkomt; de lage blokken zijn klein, "
    "zodat er leerstof overblijft. Nummers vanaf 1.500.000. "
    "Vastgelegd vóór de knip naar run 7.2.",
    gekozen,
)
exams.forget_material()
print(f"bevroren: {aantal} opgaven; het slot telt nu "
      f"{len(exams.material())} teksten")
