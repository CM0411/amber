#!/usr/bin/env python3
"""Een vraag aan Amber in de wachtrij van de kijker zetten (25 aug 2026).

  python3 brein/vraag.py claude "wat gaat goed?"     een vraag van Claude
  python3 brein/vraag.py dagboek                     de dagboekvragen van vandaag
  python3 brein/vraag.py cley "3 + 4"                zoals het venster (vraag-tab)

De kijker beantwoordt met haar echte brein; Claudes antwoorden komen in
brein/vragen-claude.jsonl, dagboekantwoorden in sessies/dagboek-amber.md.
"""
import os, sys, time

MAP = os.environ.get("AMBER_KIJKER_MAP", "/home/arch/amber-werk/brein")
WACHTRIJ = f"{MAP}/vraag-wachtrij"
DAGBOEKVRAGEN = ("wat gaat goed?", "wat gaat niet?", "hoe was je dag?")

def stel(afzender, tekst):
    os.makedirs(WACHTRIJ, exist_ok=True)
    voor = {"claude": "claude-", "dagboek": "dagboek-", "cley": ""}[afzender]
    pad = f"{WACHTRIJ}/{voor}{time.time():.2f}.txt"
    with open(pad, "w") as f:
        f.write(tekst.strip()[:200])
    time.sleep(0.02)                       # de volgorde in de wachtrij is de naam
    return pad

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("claude", "dagboek", "cley"):
        sys.exit(__doc__)
    if sys.argv[1] == "dagboek":
        for v in DAGBOEKVRAGEN:
            print("gesteld:", stel("dagboek", v))
    else:
        print("gesteld:", stel(sys.argv[1], " ".join(sys.argv[2:])))
