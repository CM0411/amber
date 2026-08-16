"""
Het uitgebreide eindverslag van een run — eenmalig, na de finish.

Anders dan maak-rapport.py (het kwartierrapport, dat altijd al klaar staat)
is dit het verslag dat je ná de finish één keer opmaakt: alle cijfers uit
het levenslog, de nameting en de foutanalyse van cijfers-bij-finish, de
vergelijking met de vorige run, en een verhaal eromheen dat door een mens
(of Claude, met Cley erbij) geschreven is. Het verhaal staat in VERHAAL
onderaan; de cijfers komen uit de bestanden. Bewust twee lagen: getallen
die niet mogen liegen, en duiding die mag veranderen.

Draaien op de Z490 (het log staat hier):
    python3 maak-eindverslag.py            → /home/arch/rapport/<run>-eindverslag.html
    python3 maak-eindverslag.py --toon     → alleen de kerncijfers op het scherm

Alleen standaardbibliotheek. Gebouwd 16 aug 2026 voor run 5.
"""

import glob
import json
import os
import re
import statistics
import subprocess
import sys
import time

RAPPORT = "/home/arch/rapport"
LOG = "/home/arch/leven.log"
GROEI_ADVIES = "/home/arch/amber-werk/fase1/groei-advies.py"

RUN = json.load(open(f"{RAPPORT}/run.json"))
NAAM = RUN["naam"]
DOEL = int(RUN["doel"])
HEK = RUN.get("hek", "?")
VENSTER = int(RUN.get("venster", 0))
MACHINE = RUN.get("machine", "?")
UIT = f"{RAPPORT}/{NAAM}-eindverslag.html"


def mooi(naam):
    """run5 → Run 5, voor koppen en tabellen."""
    return re.sub(r"(\D)(\d)", r"\1 \2", str(naam)).capitalize()


TITEL = mooi(NAAM)
CIJFERS = f"{RAPPORT}/{NAAM}-cijfers.txt"

# De vorige run: het .json.klaar met het grootste doel onder dit doel.
VORIGE = {}
for pad in glob.glob(f"{RAPPORT}/*.json.klaar"):
    try:
        v = json.load(open(pad))
    except ValueError:
        continue
    if int(v.get("doel", 0)) < DOEL and int(v.get("doel", 0)) > int(VORIGE.get("doel", -1)):
        VORIGE = v
BEGIN = int(VORIGE.get("doel", 0))

KLEUREN = {
    "ladder": "#ffc35c", "diepte2": "#5ad18f", "diepte": "#5aa7e8",
    "gemengd": "#b58ae0", "grondslag": "#e87a7a", "gesprek": "#7fe0c3",
}
GRIJS = "#9aa7c9"


def dz(n):
    """Duizendtallen met een punt: 370000 → 370.000."""
    return f"{n:,}".replace(",", ".")


# --- het levenslog -----------------------------------------------------------

def ontleed_log():
    regels = open(LOG, errors="replace").read().splitlines()
    p_proef = re.compile(r"^\s*stap\s+(\d+) \|((?:\s+\w+\s+\d+%)+)")
    p_door = re.compile(r"stap\s+(\d+) \| wereld open: (.+)$")
    p_voort = re.compile(r"^\s*(\d+:\d+)\s+stap\s+(\d+)/(\d+)\s+\d+%\s+(\d+) ms/st"
                         r"\s+nog \S+\s+(\w+)/(\d+)\s+(\S+)")
    p_hervat = re.compile(r"HERVAT bij stap (\d+)")
    p_klaar = re.compile(r"^=== klaar om (\d+:\d+:\d+) ===")
    p_keuze = re.compile(r"^\s+(\w+)/(\d+): (\d+)× \((\d+)%\)")

    curve = {}                # stap → {proefwerk: %}   (laatste telt)
    startstreep = None        # de 'stap 0'-regel bij de start van de run
    begin_regel = None
    doorbraken, voortgang, herstarts, keuzes = [], [], [], []
    startpogingen = 0
    klaar_om = None
    in_run = False
    for i, r in enumerate(regels):
        m = p_proef.match(r)
        if m:
            stap = int(m.group(1))
            scores = {n: int(v) for n, v in re.findall(r"(\w+)\s+(\d+)%", m.group(2))}
            if stap == BEGIN and begin_regel is None:
                begin_regel = i
                in_run = True
            if stap == 0 and in_run and not any(s > BEGIN for s in curve):
                startstreep = scores            # de eerste 'stap 0' na de start
            if BEGIN <= stap <= DOEL and stap > 0:
                curve[stap] = scores
            continue
        if not in_run:
            continue
        m = p_door.search(r)
        if m and BEGIN < int(m.group(1)) <= DOEL:
            doorbraken.append((int(m.group(1)), m.group(2)))
            continue
        m = p_voort.match(r)
        if m and BEGIN < int(m.group(2)) <= DOEL:
            voortgang.append({"klok": m.group(1), "stap": int(m.group(2)),
                              "ms": int(m.group(4)), "familie": m.group(5),
                              "diepte": int(m.group(6)), "score": m.group(7)})
            continue
        m = p_hervat.search(r)
        if m and BEGIN < int(m.group(1)) <= DOEL:
            # HERVAT bij BEGIN+1 is een startpoging vóór de eerste stap (zoals de
            # acht van 14 aug 2026); pas daarna telt het als herstart binnen de run
            if int(m.group(1)) == BEGIN + 1:
                startpogingen += 1
            else:
                herstarts.append(int(m.group(1)))
            continue
        m = p_klaar.match(r)
        if m and curve and max(curve) >= DOEL:
            klaar_om = m.group(1)
            continue
        m = p_keuze.match(r)
        if m and curve and max(curve) >= DOEL:
            keuzes.append((m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))))
    if not curve:
        raise RuntimeError(f"geen proefwerkregels tussen {BEGIN} en {DOEL} in {LOG}")
    curve = sorted(curve.items())
    return {"curve": curve, "startstreep": startstreep or {},
            "doorbraken": doorbraken, "voortgang": voortgang,
            "herstarts": herstarts, "startpogingen": startpogingen,
            "keuzes": keuzes, "klaar_om": klaar_om,
            "stap": max(s for s, _ in curve), "klaar": max(s for s, _ in curve) >= DOEL}


# --- de cijfers van cijfers-bij-finish ----------------------------------------

def ontleed_cijfers():
    """nameting per vakje, het geheugen per vakje, en de foutanalyse."""
    if not os.path.exists(CIJFERS):
        return None
    tekst = open(CIJFERS, errors="replace").read()
    d = {"tekst": tekst, "nameting": {}, "geheugen": {}, "geheugen_totaal": None,
         "fouten": [], "checkpoint_stap": None}
    m = re.search(r"checkpoint van stap ([\d.]+)", tekst)
    if m:
        d["checkpoint_stap"] = int(m.group(1).replace(".", ""))
    m = re.search(r"geheugen: ([\d.]+) herinneringen", tekst)
    if m:
        d["geheugen_totaal"] = int(m.group(1).replace(".", ""))
    for fam, rest in re.findall(r"^\s+(rekenen|code|puzzel)\s+((?:\d+:\s*\d+\s*)+)$", tekst, re.M):
        for g, n in re.findall(r"(\d+):\s*(\d+)", rest):
            d["geheugen"][(fam, int(g))] = int(n)
    for fam, g, pct, n in re.findall(r"(\w+)\s+graad (\d+):\s+(\d+)%\s+\((\d+)\)", tekst):
        d["nameting"][(fam, int(g))] = (int(pct), int(n))
    # foutanalyse-blokken
    for blok in re.split(r"\n(?==== \w+ graad \d+:)", tekst):
        m = re.match(r"=== (\w+) graad (\d+): (\d+) van (\d+) goed — (\d+) missers ===", blok)
        if not m:
            continue
        missers = []
        delen = re.split(r"\n--- opgave (-?\d+) ---\n", blok)
        for k in range(1, len(delen) - 1, 2):
            nummer, inhoud = delen[k], delen[k + 1]
            zij = re.search(r"^\s+zij : (.*)$", inhoud, re.M)
            goed = re.search(r"^\s+goed: (.*)$", inhoud, re.M)
            opgave = inhoud.split("\n    zij :")[0].strip()
            def kaal(t):
                # foutanalyse.py drukt met !r: de aanhalingstekens eraf voor de lezer
                t = t.strip()
                return t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in "'\"" else t
            missers.append({"nummer": int(nummer), "opgave": opgave,
                            "zij": kaal(zij.group(1)) if zij else "", "goed": kaal(goed.group(1)) if goed else ""})
        d["fouten"].append({"familie": m.group(1), "graad": int(m.group(2)),
                            "goed": int(m.group(3)), "van": int(m.group(4)),
                            "missers": missers})
    return d


def groei_advies():
    try:
        r = subprocess.run([sys.executable, GROEI_ADVIES, LOG],
                           capture_output=True, text=True, timeout=120)
        return (r.stdout or r.stderr).strip() or "(geen uitvoer)"
    except Exception as e:                    # noqa: BLE001
        return f"groei-advies niet beschikbaar: {e}"


# --- tekenwerk ----------------------------------------------------------------

def ontsnap(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def grafiek(curve, reeksen, doorbraken=(), hoog=360):
    """Eén assenstelsel, 0–100%, x van BEGIN tot DOEL — alleen deze run."""
    B, H, L, R, O = 960, hoog, 50, 110, 24
    span = max(1, DOEL - BEGIN)

    def X(stap): return L + (B - L - R) * (stap - BEGIN) / span

    def Y(pct): return (H - O) - (H - O - 12) * pct / 100
    uit = [f'<svg viewBox="0 0 {B} {H}" xmlns="http://www.w3.org/2000/svg" '
           f'style="width:100%;height:auto">']
    for pct in (0, 25, 50, 75, 100):
        y = Y(pct)
        uit.append(f'<line x1="{L}" y1="{y:.1f}" x2="{B - R}" y2="{y:.1f}" '
                   f'stroke="#1c3048" stroke-width="1"/>'
                   f'<text x="{L - 8}" y="{y + 4:.1f}" fill="#5a7a96" '
                   f'font-size="12" text-anchor="end">{pct}%</text>')
    stapgrootte = 5000 if span <= 60000 else 25000
    for stap in range(BEGIN, DOEL + 1, stapgrootte):
        x = X(stap)
        uit.append(f'<text x="{x:.1f}" y="{H - 4}" fill="#5a7a96" '
                   f'font-size="12" text-anchor="middle">{stap // 1000}k</text>')
    for stap, wat in doorbraken:
        x = X(stap)
        kort = "".join(w[0] + re.sub(r"\D", "", w) for w in wat.split(", "))
        uit.append(f'<line x1="{x:.1f}" y1="{Y(100):.1f}" x2="{x:.1f}" '
                   f'y2="{Y(0):.1f}" stroke="#2a4560" stroke-width="1" '
                   f'stroke-dasharray="3 5"/>')
    lijnen, labels = [], []
    for naam in reeksen:
        punten = [(X(s), Y(v[naam])) for s, v in curve if naam in v]
        if not punten:
            continue
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in punten)
        kleur = KLEUREN.get(naam, GRIJS)
        lx, ly = punten[-1]
        lijnen.append(f'<polyline points="{pts}" fill="none" stroke="{kleur}" '
                      f'stroke-width="{3 if naam == "ladder" else 1.6}" stroke-linejoin="round"/>'
                      f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="{kleur}"/>')
        labels.append([ly, lx, naam, kleur])
    # labels die op elkaar vallen (gesprek/grondslag/gemengd/ladder rond de 90%)
    # van boven naar beneden minstens 14 px uit elkaar duwen
    labels.sort()
    for k in range(1, len(labels)):
        if labels[k][0] - labels[k - 1][0] < 14:
            labels[k][0] = labels[k - 1][0] + 14
    uit.extend(lijnen)
    for ly, lx, naam, kleur in labels:
        uit.append(f'<text x="{lx + 8:.1f}" y="{ly + 4:.1f}" fill="{kleur}" '
                   f'font-size="13">{naam}</text>')
    uit.append("</svg>")
    return "".join(uit)


def tabel(koppen, rijen, klas=""):
    k = "".join(f"<th>{ontsnap(h)}</th>" for h in koppen)
    r = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in rij) + "</tr>" for rij in rijen)
    return f'<table class="{klas}"><tr>{k}</tr>{r}</table>'


def verschil(a, b):
    if a is None or b is None:
        return "—"
    d = b - a
    kleur = "#5ad18f" if d > 0 else ("#e87a7a" if d < 0 else "#7a9ab8")
    return f'<span style="color:{kleur}">{"+" if d > 0 else ("±" if d == 0 else "")}{d}</span>'


# --- het verslag --------------------------------------------------------------

def maak_html(d, c, verhaal, advies):
    curve = d["curve"]
    eind_stap, eind = curve[-1]
    start_stap, start = curve[0]
    # de startstreep van een proefwerk dat pas in deze run begon (gesprek)
    start = dict(start)
    for n, v in d["startstreep"].items():
        start.setdefault(n, v)
    namen_vast = ("ladder", "gesprek", "diepte2", "diepte", "gemengd", "grondslag")
    namen = [n for n in namen_vast if n in eind] + sorted(n for n in eind if n not in namen_vast)

    kaart = "".join(
        f'<div class="vak"><div class="cijfer" style="color:{KLEUREN.get(n, GRIJS)}">'
        f'{eind[n]}%</div><div class="naam">{n}</div></div>' for n in namen)

    # tempo en tijd
    laatste = d["voortgang"][-1] if d["voortgang"] else None
    ms = laatste["ms"] if laatste else None
    eerste_klok = d["voortgang"][0]["klok"] if d["voortgang"] else "?"

    # van vorige run naar deze
    rijen = []
    for n in namen:
        a, b = start.get(n), eind.get(n)
        reeks = [v[n] for _, v in curve if n in v]
        piek = max(reeks) if reeks else None
        laatste10 = reeks[-10:] if reeks else []
        rijen.append([n, f"{a}%" if a is not None else "—", f"{b}%",
                      verschil(a, b),
                      f"{statistics.mean(laatste10):.0f}% ({min(laatste10)}–{max(laatste10)})" if laatste10 else "—",
                      f"{piek}%" if piek is not None else "—"])
    vergelijking = tabel(["proefwerk", f"eind {mooi(VORIGE.get('naam', 'vorige run')).lower()}",
                          f"eind {TITEL.lower()}", "verschil", "laatste 10 metingen", "piek"], rijen)

    # nameting per vakje
    nameting_html = "<p class=\"stil\">de nameting is nog niet binnen — cijfers-bij-finish draait pas als de dienst uit is en het doel gehaald</p>"
    geheugen_html = ""
    if c and c["nameting"]:
        graden = sorted({g for _, g in c["nameting"]})
        fams = [f for f in ("rekenen", "code", "puzzel") if any(f == ff for ff, _ in c["nameting"])]
        rijen = []
        for g in graden:
            rij = [str(g)]
            for f in fams:
                nu = c["nameting"].get((f, g))
                vorig = verhaal.get("nameting_vorig", {}).get((f, g))
                cel = f"{nu[0]}%" if nu else "—"
                if nu and vorig is not None:
                    cel += f' <span class="stil">({verschil(vorig, nu[0])})</span>'
                rij.append(cel)
            rijen.append(rij)
        nameting_html = tabel(["graad"] + fams, rijen)
        n_per = next(iter(c["nameting"].values()))[1]
        nameting_html += (f'<p class="stil">grondslag-proefwerk, {n_per} opgaven per vakje, '
                          f'gemeten op de {MACHINE} na afloop; tussen haakjes het verschil met de '
                          f'nameting van {mooi(VORIGE.get("naam", "de vorige run")).lower()}</p>')
        if c["geheugen"]:
            fams_g = [f for f in ("rekenen", "code", "puzzel") if any(f == ff for ff, _ in c["geheugen"])]
            rijen = []
            for f in fams_g:
                cellen = sorted((g, n) for (ff, g), n in c["geheugen"].items() if ff == f)
                rijen.append([f, str(len(cellen)),
                              f"{min(n for _, n in cellen)}–{max(n for _, n in cellen)}",
                              f"{sum(n for _, n in cellen)}"])
            geheugen_html = (f'<p>Het geheugen: <b>{dz(c["geheugen_totaal"])} herinneringen</b> over '
                             f'{len(c["geheugen"])} vakjes.</p>'
                             + tabel(["familie", "vakjes", "per vakje (min–max)", "samen"], rijen))

    # foutanalyse
    fouten_html = ""
    if c and c["fouten"]:
        delen = []
        for blok in c["fouten"]:
            voorbeelden = "".join(
                f'<div class="misser"><pre>{ontsnap(m["opgave"])}</pre>'
                f'<div><span class="zij">zij:</span> <code>{ontsnap(m["zij"])}</code></div>'
                f'<div><span class="goed">goed:</span> <code>{ontsnap(m["goed"])}</code></div></div>'
                for m in blok["missers"][:verhaal.get("voorbeelden_per_vakje", 3)])
            uitleg = verhaal.get("fouten_uitleg", {}).get((blok["familie"], blok["graad"]), "")
            delen.append(
                f'<h3>{blok["familie"]} graad {blok["graad"]} — {blok["goed"]} van {blok["van"]} goed, '
                f'{len(blok["missers"])} missers</h3>'
                + (f"<p>{uitleg}</p>" if uitleg else "")
                + f'<details><summary class="stil">de eerste {min(len(blok["missers"]), verhaal.get("voorbeelden_per_vakje", 3))} missers voluit</summary>{voorbeelden}</details>')
        fouten_html = "".join(delen)

    # proefwerken over de tijd: elke `stapje` stappen
    stapje = verhaal.get("tabel_stap", 2500)
    rijen = []
    for s, v in curve:
        if (s - BEGIN) % stapje == 0 or s == eind_stap:
            rijen.append([dz(s)] + [f"{v[n]}%" if n in v else "—" for n in namen])
    verloop = tabel(["stap"] + namen, rijen)

    doorbraken = tabel(["stap", "doorbraak"],
                       [[dz(s), ontsnap(w)] for s, w in d["doorbraken"]]) if d["doorbraken"] else "<p class=\"stil\">geen</p>"

    if d["keuzes"]:
        # life.py deelt door het totale stapnummer (370.000); hier het aandeel
        # in de stappen van déze run, want daar gaat de telling over
        keuzes = "<ul>" + "".join(
            f"<li>{f}/{g} — {dz(n)}× ({str(round(100 * n / max(1, DOEL - BEGIN), 1)).replace('.', ',')}%)</li>"
            for f, g, n, p in d["keuzes"]) + "</ul>"
        keuzes_bron = f"uit de eindtelling van life.py over alle {dz(DOEL - BEGIN)} stappen van deze run"
    else:
        # vangnet: de steekproef uit de voortgangsregels (één op de vijftig stappen)
        tel = {}
        for v in d["voortgang"]:
            tel[(v["familie"], v["diepte"])] = tel.get((v["familie"], v["diepte"]), 0) + 1
        top = sorted(tel.items(), key=lambda x: -x[1])[:6]
        keuzes = "<ul>" + "".join(f"<li>{f}/{g} — {n}× in de steekproef</li>" for (f, g), n in top) + "</ul>"
        keuzes_bron = "steekproef: één op de vijftig stappen, uit de voortgangsregels"
    fam_tel = {}
    for v in d["voortgang"]:
        fam_tel[v["familie"]] = fam_tel.get(v["familie"], 0) + 1
    tot = sum(fam_tel.values()) or 1
    fam_verdeling = " · ".join(f"{f} {100 * n // tot}%" for f, n in sorted(fam_tel.items(), key=lambda x: -x[1]))
    # hoe goed ze het deed op wat ze zélf koos: de pogingscores in de steekproef
    # (één op de vier stappen is een poging; de voortgangsregel toont er één op de vijftig)
    poging = {}
    for v in d["voortgang"]:
        if v["score"] != "--":
            poging.setdefault(v["familie"], []).append(int(v["score"].rstrip("%")))
    poging_tekst = " · ".join(
        f"{f} {statistics.mean(x):.0f}% (n={len(x)})"
        for f, x in sorted(poging.items(), key=lambda kv: -len(kv[1])))

    nu = time.strftime("%-d %b %Y, %H:%M")
    klaar_tekst = (f"gefinisht {verhaal.get('datum_finish', time.strftime('%-d %b %Y'))} om "
                   f"{d['klaar_om'][:5] if d['klaar_om'] else (laatste['klok'] if laatste else '?')}")
    status = ('<span class="af">klaar — alle stappen gezet</span>' if d["klaar"]
              else f'<span class="loop">nog niet af — tot stap {dz(eind_stap)}</span>')

    secties = verhaal["secties"]
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITEL} — eindverslag</title>
<style>
  body {{ background:#0a1420; color:#cfe0ef; font: 16px/1.55 system-ui,
         sans-serif; max-width: 1000px; margin: 0 auto; padding: 24px; }}
  h1 {{ color:#ffc35c; font-size: 1.6rem; margin-bottom: .2rem; }}
  h2 {{ color:#8fb2d0; font-size: 1.1rem; margin-top: 2.2rem; }}
  h3 {{ color:#a9c1d8; font-size: 1rem; margin-top: 1.4rem; margin-bottom: .3rem; }}
  .af   {{ color:#5ad18f; font-weight: 600; }}
  .loop {{ color:#5aa7e8; font-weight: 600; }}
  .stil {{ color:#5a7a96; font-size: .9rem; }}
  .vakken {{ display:flex; gap:12px; flex-wrap:wrap; margin:20px 0; }}
  .vak {{ background:#101e30; border-radius:10px; padding:14px 20px;
          text-align:center; flex:1; min-width:110px; }}
  .cijfer {{ font-size:1.9rem; font-weight:700; font-variant-numeric: tabular-nums; }}
  .naam {{ color:#7a9ab8; font-size:.85rem; }}
  .zorg {{ background:#2a1a1a; border-left:4px solid #e87a7a; padding:10px 14px; border-radius:6px; }}
  .goednieuws {{ background:#12281e; border-left:4px solid #5ad18f; padding:10px 14px; border-radius:6px; }}
  .advies {{ background:#151a2a; border-left:4px solid #6f8fd6; padding:10px 14px;
            font-size:13px; white-space:pre-wrap; overflow-x:auto; }}
  table {{ border-collapse:collapse; font-variant-numeric: tabular-nums; }}
  td, th {{ padding:4px 18px 4px 0; border-bottom:1px solid #1c3048; text-align:left; vertical-align:top; }}
  th {{ color:#7a9ab8; font-weight:600; }}
  .graf {{ background:#0d1826; border-radius:12px; padding:16px; overflow-x:auto; }}
  .misser {{ background:#0d1826; border-radius:8px; padding:8px 12px; margin:8px 0; font-size:.9rem; }}
  .misser pre {{ white-space:pre-wrap; margin:0 0 6px 0; color:#a9c1d8; }}
  .zij {{ color:#e87a7a; }} .goed {{ color:#5ad18f; }}
  code {{ font-size:.85rem; }}
  details summary {{ cursor:pointer; }}
  .scroll {{ overflow-x:auto; }}
  ul {{ padding-left: 1.2rem; }}  li {{ margin: .25rem 0; }}
</style></head><body>
<h1>{TITEL} — eindverslag</h1>
<p>{status} &nbsp;·&nbsp; {klaar_tekst} &nbsp;·&nbsp;
   <span class="stil">stap {dz(BEGIN)} → {dz(DOEL)} ({dz(DOEL - BEGIN)} stappen in deze run) ·
   {ms if ms else '?'} ms per stap op de {MACHINE} · venster {VENSTER} · hek: {HEK}</span></p>
<div class="vakken">{kaart}</div>

<h2>Samenvatting</h2>
{secties["samenvatting"]}

<h2>Wat {TITEL.lower()} was</h2>
{secties["opzet"]}

<h2>Van {mooi(VORIGE.get("naam", "de vorige run")).lower()} naar {TITEL.lower()}</h2>
<div class="scroll">{vergelijking}</div>
<p class="stil">"eind {mooi(VORIGE.get("naam", "vorige")).lower()}" is de meting op stap {dz(BEGIN)} vóór de start; voor een proefwerk
dat pas in deze run begon (gesprek) staat daar de startstreep van de eerste meting.
"laatste 10 metingen" is het gemiddelde met de laagste en hoogste erachter — lees geen
verschillen van een paar procent uit één meting.</p>

<h2>Nameting per vakje — stap {dz(c["checkpoint_stap"]) if c and c.get("checkpoint_stap") else dz(DOEL)}</h2>
<div class="scroll">{nameting_html}</div>
{geheugen_html}
{secties.get("nameting", "")}

<h2>Waar de fouten zitten</h2>
{secties["fouten"]}
{fouten_html}

<h2>Waar de verbeteringen zitten</h2>
{secties["verbeteringen"]}

<h2>Proefwerken over de tijd</h2>
<div class="graf">{grafiek(curve, namen, d["doorbraken"])}</div>
<p class="stil">De stippellijnen zijn doorbraken: momenten waarop ze zelf een diepte openmaakte.
Elke meting is exact dezelfde bevroren opgavenlijst, dus de lijnen zijn over de hele run
vergelijkbaar. Tabel: elke {dz(stapje)} stappen; het volledige verloop per 500 staat in leven.md op de trainer.</p>
<div class="scroll">{verloop}</div>

<h2>Doorbraken — waar de wereld openging</h2>
<div class="scroll">{doorbraken}</div>
{secties.get("doorbraken", "")}

<h2>Waar ze zelf voor koos</h2>
<p class="stil">{keuzes_bron}; verdeling over de families in de steekproef: {fam_verdeling}</p>
{keuzes}
<p>Hoe goed ze het deed op wat ze zélf koos — de score van haar pogingen in diezelfde steekproef,
op stof uit haar eigen wereld en niet uit een bevroren blad: {poging_tekst}.</p>
{secties.get("keuzes", "")}

<h2>Naast de run gemeten</h2>
{secties["naast"]}

<h2>Groei-advies (E)</h2>
<pre class="advies">{ontsnap(advies)}</pre>
<p class="stil">Vlak + meters niet vol + wereld dicht → "overweeg een laag"; anders wat er wél speelt.
Een voorstel, geen automatisme — Cley beslist.</p>

<h2>Bedrijf</h2>
<p>Gedraaid op de {MACHINE} · eerste voortgangsregel {eerste_klok}, laatste {laatste['klok'] if laatste else '?'} ·
tempo {ms if ms else '?'} ms per stap (lopend gemiddelde over de hele run) ·
startpogingen vóór de eerste stap: {d["startpogingen"]} · herstarts ná de eerste stap: {len(d["herstarts"])}{(" (bij stap " + ", ".join(dz(h) for h in d["herstarts"]) + ")") if d["herstarts"] else ""} ·
{len(d["doorbraken"])} doorbraken.</p>
{secties.get("bedrijf", "")}

<h2>En nu</h2>
{secties["nu"]}

<p class="stil">eindverslag opgemaakt {nu}, na afloop van de run · maak-eindverslag.py leest leven.log,
{os.path.basename(CIJFERS)} en run.json; het verhaal is geschreven door Claude in de nacht van de finish, op Cleys verzoek</p>
</body></html>"""


def hoofd():
    d = ontleed_log()
    c = ontleed_cijfers()
    if "--toon" in sys.argv:
        print(f"{NAAM}: {dz(BEGIN)} → {dz(d['stap'])} van {dz(DOEL)} "
              f"({'klaar' if d['klaar'] else 'loopt'})")
        print("eind:", d["curve"][-1][1])
        print("startstreep:", d["startstreep"])
        print("doorbraken:", len(d["doorbraken"]), "herstarts:", d["herstarts"])
        print("keuzes:", d["keuzes"][:6])
        print("klaar om:", d["klaar_om"])
        if c:
            print("nameting:", sorted(c["nameting"].items()))
            print("geheugen:", c["geheugen_totaal"])
            print("fouten:", [(f["familie"], f["graad"], f["goed"], f["van"], len(f["missers"])) for f in c["fouten"]])
        return 0
    from verhaal_run import VERHAAL           # het verhaal van deze run, apart bestand
    html = maak_html(d, c, VERHAAL, groei_advies())
    with open(UIT + ".deel", "w") as f:
        f.write(html)
    os.replace(UIT + ".deel", UIT)
    print(f"eindverslag geschreven: {UIT} (stap {dz(d['stap'])}, "
          f"{'klaar' if d['klaar'] else 'nog niet af'}, "
          f"cijfers {'binnen' if c and c['nameting'] else 'nog niet binnen'})")
    return 0


if __name__ == "__main__":
    sys.exit(hoofd())
