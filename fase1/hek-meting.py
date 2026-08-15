"""Hekmeting — hoe diep mag de wereld open bij een groter venster?

De hekken in world.py (MAX_DEPTH en MAX_DEPTH_PER) horen bij één venster:
38/15/9 is gemeten voor 1024 (run 5). De regel sinds 10 aug 2026: een
diepte gaat open als ten minste 85% van de bruikbare opgaven mét
uitwerking in `venster − 112` past (dezelfde ruimte die de leerlus
meegeeft aan `world.learning_tasks`). Daarnaast moet een diepte genoeg
opgeven om niet leeg te zijn: `learning_tasks` zoekt 64 taken in ~2300
nummers, dus onder ~5% bruikbaar loopt de leerlus daar vast (code 9 was
op 10 aug een lege kamer met 4%).

Dit script telt dat voor meerdere vensters tegelijk, alleen op de CPU,
zonder torch: per familie en diepte N opgaven maken, tellen hoeveel
bruikbaar zijn (een uitwerking komt eruit), hoeveel daarvan passen per
venster, en hoe lang de uitwerking is (dat bepaalt de pogingtijd — één
treuzelaar bepaalt de duur van een poging, 15 aug). Onderaan per venster
het hek per familie volgens de 85%-regel.

MAX_DEPTH in world.py begrenst `make()`; hier tijdelijk opgerekt in het
proces zelf zodat we voorbij de huidige hekken kunnen kijken. Er wordt
niets weggeschreven en world.py blijft onaangeroerd.

  venv/bin/python fase1/hek-meting.py [N=200] [vensters=1024,1536,2048]
"""
import statistics
import sys
import time

sys.path.insert(0, "/home/arch/amber-werk/kern")
import world

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
VENSTERS = ([int(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2
            else [1024, 1536, 2048])
MARGE = 112                      # learning.py: room = window - 112
MAAT = 0.85                      # de 85%-regel van 10 aug 2026
LEEG = 0.10                      # lege kamer: learning_tasks haalt 64 in ~2300
                                 # nummers nog nét bij 5%, maar dan is elke
                                 # partij dezelfde handvol opgaven
START = 3_000_000                # ver van proefwerk- en leernummers

# hoe diep kijken: van net onder het huidige hek tot ruim erboven
BEREIK = {"rekenen": range(30, 91, 2),
          "code": range(12, 31),
          "puzzel": range(7, 17)}

HEK_NU = {"rekenen": world.MAX_DEPTH}
HEK_NU.update(world.MAX_DEPTH_PER)
world.MAX_DEPTH = 200            # alleen in dit proces; make() leest de global

print(f"hekmeting · N={N} per vakje · vensters {VENSTERS} · "
      f"huidige hekken {HEK_NU}")
print(f"past = opgave + uitwerking + 3 <= venster - {MARGE}; "
      f"hek = diepste diepte waar >= {MAAT:.0%} van bruikbaar past "
      f"(en bruikbaar >= {LEEG:.0%})\n")

hek = {v: {} for v in VENSTERS}
t0 = time.time()
for fam, dieptes in BEREIK.items():
    kop = f"{'diepte':>6} {'bruikb':>7}"
    for v in VENSTERS:
        kop += f" {'past@' + str(v):>10}"
    kop += f" {'lengte med':>10} {'max':>5} {'uitw med':>8}"
    print(f"— {fam} (hek nu {HEK_NU[fam]}) —")
    print(kop)
    for d in dieptes:
        lengtes, uitw = [], []
        bruikbaar = fouten = 0
        for n in range(START, START + N):
            try:
                t = world.make(fam, d, n)
            except Exception:
                fouten += 1
                continue
            if t is None:
                continue
            bruikbaar += 1
            lengtes.append(len(t.problem) + len(t.to_learn()) + 3)
            uitw.append(len(t.working or ""))
        aandeel = bruikbaar / N
        regel = f"{d:>6} {aandeel:>6.0%} "
        for v in VENSTERS:
            if bruikbaar:
                past = sum(l <= v - MARGE for l in lengtes) / bruikbaar
                regel += f" {past:>9.0%} "
                if past >= MAAT and aandeel >= LEEG:
                    hek[v][fam] = d          # dieptes lopen op → laatste die haalt
            else:
                regel += f" {'-':>9} "
        if lengtes:
            regel += (f" {statistics.median(lengtes):>10.0f} {max(lengtes):>5}"
                      f" {statistics.median(uitw):>8.0f}")
        if fouten:
            regel += f"   ({fouten} fouten)"
        print(regel, flush=True)
    print()

print(f"— hekken volgens de {MAAT:.0%}-regel ({time.time() - t0:.0f} s) —")
for v in VENSTERS:
    delen = []
    for fam in BEREIK:
        h = hek[v].get(fam)
        nu = HEK_NU[fam]
        # onder het bereik gemeten? dan is het hek van nu het antwoord
        delen.append(f"{fam} {h if h else f'<{min(BEREIK[fam])}'}"
                     f" (nu {nu})")
    print(f"  venster {v}: " + ", ".join(delen))
print("\nLet op: dit is 'past het'; of de diepste dieptes ook léérbaar zijn "
      "en wat de langere uitwerking aan pogingtijd kost, is een aparte "
      "vraag (tempo-proef op de trainer).")
print("En: code wordt voorbij ~15 niet dieper — de grammatica plafonneert "
      "(regels 6, lijst 9, def 15 rondes; alleen de lus groeit mee). Een "
      "hoger hek voor code is dus geen diepere wereld; dat vraagt nieuwe "
      "bouwstenen in world.py, geen venster.")
