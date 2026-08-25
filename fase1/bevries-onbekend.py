"""Bevriest het proefwerkblad "onbekend" (25 aug 2026, Claudes eerste wens):
veertig opgaven die niemand kan weten, twaalf dieptes, nummers onder de
proefwerkgrens. Het cijfer op dit blad is het aandeel eerlijke "?".

Draaien op een rungrens, vóór de start van de run die het blad krijgt:
  python3 fase1/bevries-onbekend.py            (schrijft proefwerken/onbekend.json)
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kern"))
import determinism
import exams, world

if exams.exists("onbekend"):
    sys.exit("proefwerken/onbekend.json bestaat al — een blad verandert nooit")
opgaven = []
n = 0
for depth in range(1, 13):
    for _ in range(4 if depth <= 4 else 3):
        opgaven.append(world.make("onbekend", depth, n)); n += 1
    if len(opgaven) >= 40:
        break
opgaven = opgaven[:40]
exams.freeze("onbekend", "opgaven die niemand kan weten; het eerlijke antwoord is ? (25 aug 2026)", opgaven, window=512)
print(f"bevroren: onbekend, {len(opgaven)} opgaven, dieptes 1..{max(t.grade for t in opgaven)}")
