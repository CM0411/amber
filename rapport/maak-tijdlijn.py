"""De tijdlijn — haar geschiedenis over alle runs heen (18 aug 2026, Cleys
wens): één bestand /home/arch/rapport/tijdlijn.json waar het venster
(/tijdlijn) uit tekent. Bronnen die er al zijn:

  * leven.log — elke proefwerkregel (`stap N | naam pct% …`; de startregel
    `stap 0` van een run wordt aan de HERVAT-stap ervoor gehangen), elke
    wereldopening (`stap N | wereld open: familie tot D`), de lesregels;
  * rapport/run.json — de lopende run; een nieuwe naam sluit de vorige af;
  * rapport/tijdlijn-gebeurtenissen.json — de gecureerde geschiedenis
    (runs tot nu toe met vorm en hekken, en de gebeurtenissen met de hand
    ingeprikt uit BESLUITEN.md).

Het bestand groeit alleen aan: wat er ooit in stond blijft, ook als
leven.log later wordt afgekapt. Draait elk kwartier mee met het rapport
(amber-rapport.service). Alleen lezen en schrijven in ~/rapport — niets
raakt de trainer.

  python3 maak-tijdlijn.py
"""
import json
import os
import re
import time

RAPPORT = "/home/arch/rapport"
LOG = "/home/arch/leven.log"
UIT = f"{RAPPORT}/tijdlijn.json"
GECUREERD = "/home/arch/amber-werk/rapport/tijdlijn-gebeurtenissen.json"


def lees_json(pad, anders):
    try:
        with open(pad) as f:
            return json.load(f)
    except Exception:
        return anders


def hekken_van(tekst):
    return {f: int(d) for f, d in re.findall(r"(\w+) (\d+)", tekst or "")}


bestaand = lees_json(UIT, {})
gecureerd = lees_json(GECUREERD, {"runs": [], "gebeurtenissen": []})
runjson = lees_json(f"{RAPPORT}/run.json", {})

# --- 1. runs: gecureerd + wat run.json erbij zegt ------------------------------
runs = {r["naam"]: dict(r) for r in gecureerd.get("runs", [])}
for r in bestaand.get("runs", []):
    runs.setdefault(r["naam"], dict(r))            # eerder automatisch gevonden
naam_nu = runjson.get("naam")
if naam_nu and naam_nu not in runs:
    # een nieuwe run: de vorige krijgt zijn eind, deze zijn begin uit run.json
    runs[naam_nu] = {"naam": naam_nu, "start": runjson.get("start"), "eind": None,
                     "datum": time.strftime("%Y-%m-%d"),
                     "venster": runjson.get("venster"), "lagen": runjson.get("lagen"),
                     "hek": runjson.get("hek"), "families": sorted(hekken_van(runjson.get("hek"))),
                     "noot": "automatisch uit run.json"}
runs_lijst = sorted(runs.values(), key=lambda r: (r.get("start") or 0))
for a, b in zip(runs_lijst, runs_lijst[1:]):
    if a.get("eind") is None:
        a["eind"] = b.get("start")
if naam_nu and runs.get(naam_nu):
    r = runs[naam_nu]
    for k in ("venster", "lagen", "hek"):
        if runjson.get(k) is not None:
            r[k] = runjson.get(k)
    r["families"] = sorted(hekken_van(runjson.get("hek"))) or r.get("families", [])
    r["doel"] = runjson.get("doel")


def run_bij(stap):
    for r in runs_lijst:
        if (r.get("start") or 0) <= stap and (r.get("eind") is None or stap < r["eind"]):
            return r
    return None


# --- 2. leven.log: proefwerken, wereld, lessen, herstarts ---------------------
punten = {int(k): v for k, v in (bestaand.get("punten") or {}).items()}
wereld = {k: {int(s): d for s, d in v.items()} for k, v in (bestaand.get("wereld") or {}).items()}
gebeurtenissen = {(g["stap"], g["tekst"]): g for g in bestaand.get("gebeurtenissen", [])}
for g in gecureerd.get("gebeurtenissen", []):
    gebeurtenissen[(g["stap"], g["tekst"])] = dict(g)

try:
    regels = open(LOG, encoding="utf-8", errors="ignore").read().splitlines()
except OSError:
    regels = []
hervat = None
familie_gezien = {f for v in wereld.values() for f in [v] if False}
gezien_fam = set(k for k in wereld)
for regel in regels:
    m = re.match(r"HERVAT bij stap (\d+)", regel.strip())
    if m:
        hervat = int(m.group(1)) - 1
        continue
    m = re.match(r"\s+stap\s+(\d+) \|((?:\s+[\w-]+\s+\d+%)+)", regel)
    if m:
        st = int(m.group(1))
        if st == 0:
            if hervat is None:
                continue
            st = hervat
        scores = {n: int(p) for n, p in re.findall(r"([\w-]+)\s+(\d+)%", m.group(2))}
        punten[st] = scores                    # de laatste meting op die stap wint
        continue
    m = re.match(r"\s+stap\s+(\d+) \| wereld open: (.+)", regel)
    if m:
        st = int(m.group(1))
        for fam, d in re.findall(r"(\w+) tot (\d+)", m.group(2)):
            d = int(d)
            wereld.setdefault(fam, {})[st] = d
            r = run_bij(st)
            hek = hekken_van(r.get("hek")) if r else {}
            if fam not in gezien_fam:
                gezien_fam.add(fam)
            if hek.get(fam) == d:
                gebeurtenissen[(st, f"hek bereikt: {fam} {d}")] = {
                    "stap": st, "soort": "hek", "tekst": f"hek bereikt: {fam} {d}",
                    "datum": r.get("datum") if r else None}
        continue
    m = re.match(r"\s+lessen van Cley: (.+)", regel)
    if m and hervat is not None:
        gebeurtenissen[(hervat, "lessen: " + m.group(1)[:80])] = {
            "stap": hervat, "soort": "les", "tekst": "lessen: " + m.group(1)[:80]}

# de proefwerkpunten voorbij de laatste bekende stap zijn ruis (bv. een
# meetscript dat in het logboek schreef): houd wat vóór het eind van de
# lopende run ligt of erin
laatste_run = runs_lijst[-1] if runs_lijst else None
if laatste_run and runjson.get("doel"):
    punten = {s: v for s, v in punten.items() if s <= int(runjson["doel"])}

# --- 3. schrijven ---------------------------------------------------------------
uit = {
    "gemaakt": time.strftime("%Y-%m-%d %H:%M"),
    "runs": runs_lijst,
    "punten": {str(s): punten[s] for s in sorted(punten)},
    "wereld": {f: {str(s): d for s, d in sorted(v.items())} for f, v in wereld.items()},
    "gebeurtenissen": sorted(gebeurtenissen.values(), key=lambda g: (g["stap"], g.get("soort", ""))),
    "bladen": sorted({n for v in punten.values() for n in v}),
}
with open(UIT + ".deel", "w") as f:
    json.dump(uit, f, ensure_ascii=False)
os.replace(UIT + ".deel", UIT)
print(f"tijdlijn: {len(punten)} proefwerkpunten, {len(runs_lijst)} runs, "
      f"{len(uit['gebeurtenissen'])} gebeurtenissen, wereld {sorted(wereld)}")
