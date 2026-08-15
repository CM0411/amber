"""Het groeisignaal (E, fase 5) — zit ze vast, en is dat een capaciteitsvraag?

De roadmap zegt "capaciteit erbij wanneer ze vastloopt" en laat open wat
vastlopen is. Dit is een eerste, meetbare lezing (15 aug 2026), gebouwd op
wat het log al vertelt. Drie vragen over het laatste venster van K
proefwerkmetingen (K = 20 is 10.000 stappen):

  1. **Is ze vlak?** De best stijgende meter stijgt minder dan DREMPEL
     punten (gemiddelde van de laatste vijf tegen de eerste vijf van het
     venster). Stijgt er nog iets, dan is ze niet vast.
  2. **Zijn de meters niet vol?** Minstens één proefwerk staat onder VOL.
     Staan ze allemaal (bijna) op 100, dan meet niets meer iets — dan is
     het antwoord een nieuwe meter of een grotere wereld, geen laag
     (les van 15 aug: diepte2 en ladder waren vol, geen leerprobleem).
  3. **Gaat de wereld nog open?** Een "wereld open"-regel in het venster
     betekent dat ze nog terrein wint; dan is ze niet vast.

Alleen als alle drie ja zeggen luidt het advies: overweeg een laag.
Anders zegt het wat er wél aan de hand is. Het advies is een voorstel —
zij (of dit script) stelt voor, Cley beslist; groeien gebeurt op een
rungrens met `rungrens.py --lagen`.

Bekende beperking: een meter kan onder VOL vlak staan omdat zijn opgaven
niet oplosbaar zijn (diepte2 puzzel 6/9). Dan lijkt dit een capaciteits-
vraag terwijl het een meterprobleem is; foutanalyse.py wijst dat uit.

  venv/bin/python fase1/groei-advies.py [leven.log] [K=20]
  venv/bin/python fase1/groei-advies.py --trainer          (haalt het log op)
"""
import re
import subprocess
import sys

K = 20
DREMPEL = 2.0          # punten stijging over het venster die nog "groei" heet
VOL = 90               # daarboven telt een meter als (bijna) vol
# Versleten meters (15 aug 2026): hun plafond ligt onder 100 doordat een
# deel van de opgaven niet oplosbaar is. Vol = op het plafond. `diepte`
# (oude schrijfwijze, 9 aug) heeft geen gemeten plafond en telt niet mee.
PLAFOND = {"diepte2": 81, "ladder": 91}
NEGEER = {"diepte"}

args = [x for x in sys.argv[1:] if not x.startswith("--")]
if "--trainer" in sys.argv:
    geheim = open("/home/arch/.amber-geheim").read().strip()
    log = subprocess.run(["sshpass", "-p", geheim, "ssh", "-o",
                          "ConnectTimeout=8", "arch@192.168.1.239",
                          "cat ~/leven.log"], capture_output=True,
                         text=True, timeout=60).stdout
else:
    log = open(args[0] if args else "/home/arch/leven.log",
               errors="replace").read()
if len(args) > 1:
    K = int(args[1])

# --- dezelfde ontleding als het rapport (maak-rapport.py) --------------------
regels = log.splitlines()
p_proef = re.compile(r"stap\s+(\d+) \|((?:\s+\w+\s+\d+%)+)")
proef = []
for i, r in enumerate(regels):
    m = p_proef.search(r)
    if m:
        proef.append((i, int(m.group(1)),
                      {n: int(v) for n, v in
                       re.findall(r"(\w+)\s+(\d+)%", m.group(2))}))
kern = [p for p in proef if p[1] > 0]
staart = []
for p in reversed(kern):
    if staart and p[1] >= staart[-1][1]:
        break
    staart.append(p)
staart.reverse()
if len(staart) < 10:
    sys.exit(f"te weinig proefwerkmetingen in deze run ({len(staart)})")
begin_regel = staart[0][0]
curve = {}
for _, stap, scores in staart:
    curve[stap] = scores
curve = sorted(curve.items())
venster = curve[-K:]
stap_van, stap_tot = venster[0][0], venster[-1][0]

# --- 1. vlak? -----------------------------------------------------------------
namen = sorted({n for _, s in venster for n in s})
stijging = {}
for n in namen:
    reeks = [s[n] for _, s in venster if n in s]
    if len(reeks) < 10:
        continue
    stijging[n] = sum(reeks[-5:]) / 5 - sum(reeks[:5]) / 5
beste = max(stijging.values()) if stijging else 0.0
vlak = beste < DREMPEL

# --- 2. meters niet vol? -------------------------------------------------------
laatste = {n: sum([s[n] for _, s in venster if n in s][-5:]) / 5
           for n in stijging}
niet_vol = [n for n, v in laatste.items()
            if n not in NEGEER and v < min(VOL, PLAFOND.get(n, 100) - 2)]

# --- 3. wereld nog open? ------------------------------------------------------
p_door = re.compile(r"stap\s+(\d+) \| wereld open: (\w+) tot (\d+)")
open_in_venster = []
for r in regels[begin_regel:]:
    m = p_door.search(r)
    if m and stap_van <= int(m.group(1)) <= stap_tot:
        open_in_venster.append((int(m.group(1)), m.group(2), int(m.group(3))))

# --- het advies -------------------------------------------------------------
print(f"groei-advies · venster stap {stap_van:,}–{stap_tot:,} "
      f"({len(venster)} metingen)".replace(",", "."))
print(f"{'proefwerk':>10} {'nu':>5} {'stijging':>9}")
for n in namen:
    if n in stijging:
        noot = ("  (plafond %d)" % PLAFOND[n] if n in PLAFOND
                else "  (telt niet mee)" if n in NEGEER else "")
        print(f"{n:>10} {laatste[n]:>4.0f}% {stijging[n]:>+8.1f}{noot}")
print()
print(f"1. vlak?            {'ja' if vlak else 'nee'} — beste stijging "
      f"{beste:+.1f} punten (drempel {DREMPEL})")
print(f"2. meters niet vol? {'ja' if niet_vol else 'nee'} — onder {VOL}% "
      f"of onder hun plafond: {', '.join(niet_vol) if niet_vol else 'geen'}")
print(f"3. wereld nog open? {'ja' if open_in_venster else 'nee'}"
      + (" — " + ", ".join(f"{f} tot {t} (stap {s:,})".replace(",", ".")
                          for s, f, t in open_in_venster)
         if open_in_venster else ""))
print()
if vlak and niet_vol and not open_in_venster:
    print("ADVIES: vastgelopen bij een open wereld en meters die nog ruimte "
          "hebben — overweeg een laag op de volgende rungrens "
          "(rungrens.py --lagen). Eerst foutanalyse.py op de vlakke meters: "
          "is het kunnen, of zijn de opgaven niet oplosbaar?")
elif not vlak:
    print("GEEN GROEI NODIG: ze stijgt nog.")
elif not niet_vol:
    print("GEEN LAAG: alle meters staan (bijna) vol — dit is een meter- of "
          "wereldvraag (nieuw proefwerk, diepere wereld), geen "
          "capaciteitsvraag.")
else:
    print("NOG NIET: vlak, maar de wereld ging in dit venster nog open — "
          "geef haar de tijd om het nieuwe terrein te nemen; kijk over "
          "5.000 stappen opnieuw.")
