"""
De eindrapport-maker van run 3.

Draait op de Z490 (sinds 14 aug 2026), elk kwartier (amber-rapport.timer).
Leest het levenslog van deze machine, ontleedt het, en schrijft één
zelfstandig HTML-bestand naar
/home/arch/rapport/ — zolang de run loopt als tussenstand, en zodra stap
170.000 binnen is (of de dienst gestopt is op het eindpunt) als definitief
eindrapport. Het rapport hoeft dus nooit "gemaakt" te worden: het staat er
al op het moment dat iemand komt kijken.

Alleen standaardbibliotheek. Het log is de enige waarheid; is de trainer
onbereikbaar, dan blijft het vorige rapport gewoon staan.
"""

import re
import subprocess
import sys
import time

X399 = "arch@192.168.1.239"
GEHEIM_PAD = "/home/arch/.amber-geheim"
DOEL_INDEX = "/home/arch/rapport/index.html"

# Run-instellingen uit een klein configbestand, zodat een nieuwe run alleen
# dit bestand hoeft te schrijven en niet dit script. Ontbreekt het, dan
# gelden de waarden van run 3 — het rapport valt dus nooit stil.
import json
try:
    with open("/home/arch/rapport/run.json") as f:
        _RUN = json.load(f)
except (FileNotFoundError, ValueError):
    _RUN = {}
NAAM = _RUN.get("naam", "run3")
TOTAAL = int(_RUN.get("doel", 170_000))
HEK = _RUN.get("hek", "rekenen 17, code 8, puzzel 5")
VENSTER = int(_RUN.get("venster", 512))
# haar vorm, sinds 15 aug 2026 in run.json (E: ze kan groeien)
VORM_TEKST = ""
if _RUN.get("lagen"):
    VORM_TEKST = f" · {_RUN['lagen']} lagen"
    if _RUN.get("parameters"):
        VORM_TEKST += (f", {_RUN['parameters'] / 1e6:.1f} M parameters"
                       .replace(".", ","))
    if _RUN.get("checkpointing"):
        VORM_TEKST += " · checkpointing aan"
DOEL = f"/home/arch/rapport/{NAAM}.html"

KLEUREN = {  # op donkerblauw; identiteit zit ook in de eindlabels, niet
    "ladder": "#ffc35c",       # alleen in kleur
    "diepte2": "#5ad18f",
    "diepte": "#5aa7e8",
    "gemengd": "#b58ae0",
    "grondslag": "#e87a7a",
    "gesprek": "#7fe0c3",
}
GRIJS = "#9aa7c9"              # vangnet voor een proefwerk zonder eigen kleur


def haal_log():
    # sinds 14 aug 2026 draait dit op de Z490 zelf — het log staat hier
    with open("/home/arch/leven.log", errors="replace") as f:
        return f.read()


def ontleed(log):
    """Alles wat het rapport nodig heeft, uit het log.

    Het log loopt door over runs en herstarts heen. De run-3-regels zijn de
    langste staart waarin de proefwerkstappen oplopen — dezelfde truc als in
    server.py. Herstartregels met stap 0 doen niet mee aan de staart maar
    tellen wél als herstart.
    """
    regels = log.splitlines()
    proef = []          # (regelnr, stap, {naam: score})
    # De namen komen uit de regel zelf: een vaste opsomming liep op 14 aug
    # 2026 stuk toen "gesprek" tussen de proefwerken verscheen en geen
    # enkele run-5-regel meer herkend werd. Nieuwe proefwerken doen nu
    # vanzelf mee.
    p_proef = re.compile(r"stap\s+(\d+) \|((?:\s+\w+\s+\d+%)+)")
    for i, r in enumerate(regels):
        m = p_proef.search(r)
        if m:
            stap = int(m.group(1))
            proef.append((i, stap, {
                n: int(v) for n, v in re.findall(r"(\w+)\s+(\d+)%",
                                                 m.group(2))}))

    # De staart: van achteren terug zolang de stappen blijven dalen.
    kern = [p for p in proef if p[1] > 0]
    staart = []
    for p in reversed(kern):
        if staart and p[1] >= staart[-1][1]:
            break
        staart.append(p)
    staart.reverse()
    if not staart:
        raise RuntimeError("geen proefwerkregels gevonden")
    begin_regel = staart[0][0]

    # Bij een herstart kunnen stappen dubbel voorkomen; de laatste telt.
    curve = {}
    for _, stap, scores in staart:
        curve[stap] = scores
    curve = sorted(curve.items())

    doorbraken = []
    p_door = re.compile(r"stap\s+(\d+) \| wereld open: (\w+) tot (\d+)")
    herstarts = 0
    for i, r in enumerate(regels):
        if i < begin_regel:
            continue
        m = p_door.search(r)
        if m:
            doorbraken.append((int(m.group(1)), m.group(2), int(m.group(3))))
        if re.match(r"\s*stap\s+0 \|", r):
            herstarts += 1

    # De laatste voortgangsregel: tempo en stand van dit moment.
    p_run = re.compile(r"(\d+:\d+)\s+stap\s+(\d+)/\d+\s+\d+%\s+(\d+) ms/st")
    laatste = None
    for r in regels[begin_regel:]:
        m = p_run.search(r)
        if m:
            laatste = {"klok": m.group(1), "stap": int(m.group(2)),
                       "ms": int(m.group(3))}

    stap_nu = max(curve[-1][0], laatste["stap"] if laatste else 0)
    return {"curve": curve, "doorbraken": doorbraken, "herstarts": herstarts,
            "laatste": laatste, "stap": stap_nu, "klaar": stap_nu >= TOTAAL}


def _lijn(punten, kleur, naam, dik=False):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in punten)
    laatst_x, laatst_y = punten[-1]
    return (f'<polyline points="{pts}" fill="none" stroke="{kleur}" '
            f'stroke-width="{3 if dik else 1.6}" stroke-linejoin="round"/>'
            f'<circle cx="{laatst_x:.1f}" cy="{laatst_y:.1f}" r="3" fill="{kleur}"/>'
            f'<text x="{laatst_x + 8:.1f}" y="{laatst_y + 4:.1f}" fill="{kleur}" '
            f'font-size="13">{naam}</text>')


def _merktekens():
    """Gebeurtenissen met een stapnummer (zoals de machinewissel bij
    208.500) horen zichtbaar in de grafiek — het verhaal moet ook in de
    geschiedenis kloppen."""
    try:
        vast = json.load(open("/home/arch/rapport/gebeurtenissen.json"))["vast"]
        per_stap = {}
        for g in vast:
            if not g.get("stap"):
                continue
            # bij meerdere gebeurtenissen op dezelfde stap wint de
            # verhuizing — dat is het merkteken dat het verhaal vertelt
            if g["stap"] not in per_stap or "Z490" in g["wat"]:
                per_stap[g["stap"]] = g["wat"]
        return sorted(per_stap.items())
    except Exception:
        return []


def grafiek(curve, reeksen, doorbraken=None, hoog=300):
    """Eén assenstelsel, 0–100%, x altijd 0–170.000 zodat je ziet hoe ver
    de run is. Dunne lijnen, label aan het eind, raster onopvallend."""
    B, H, L, R, O = 960, hoog, 50, 110, 24
    def X(stap): return L + (B - L - R) * stap / TOTAAL
    def Y(pct): return (H - O) - (H - O - 12) * pct / 100
    uit = [f'<svg viewBox="0 0 {B} {H}" xmlns="http://www.w3.org/2000/svg" '
           f'style="width:100%;height:auto">']
    for pct in (0, 25, 50, 75, 100):
        y = Y(pct)
        uit.append(f'<line x1="{L}" y1="{y:.1f}" x2="{B - R}" y2="{y:.1f}" '
                   f'stroke="#1c3048" stroke-width="1"/>'
                   f'<text x="{L - 8}" y="{y + 4:.1f}" fill="#5a7a96" '
                   f'font-size="12" text-anchor="end">{pct}%</text>')
    for stap in range(0, TOTAAL + 1, 25_000):
        x = X(stap)
        uit.append(f'<text x="{x:.1f}" y="{H - 4}" fill="#5a7a96" '
                   f'font-size="12" text-anchor="middle">{stap // 1000}k</text>')
    if doorbraken:
        for stap, fam, tot in doorbraken:
            x = X(stap)
            uit.append(f'<line x1="{x:.1f}" y1="{Y(100):.1f}" x2="{x:.1f}" '
                       f'y2="{Y(0):.1f}" stroke="#2a4560" stroke-width="1" '
                       f'stroke-dasharray="3 5"/>'
                       f'<text x="{x:.1f}" y="{Y(100) - 6:.1f}" fill="#7a9ab8" '
                       f'font-size="11" text-anchor="middle">{fam[0]}{tot}</text>')
    gezien = set()
    for stap, wat in _merktekens():
        if not 0 < stap <= TOTAAL or stap in gezien:
            continue
        gezien.add(stap)
        x = X(stap)
        naam = "→ Z490" if "Z490" in wat else wat[:14]
        uit.append(f'<line x1="{x:.1f}" y1="{Y(100):.1f}" x2="{x:.1f}" '
                   f'y2="{Y(0):.1f}" stroke="#c8873d" stroke-width="1.4" '
                   f'stroke-dasharray="7 4"/>'
                   f'<text x="{x + 5:.1f}" y="{Y(96):.1f}" fill="#c8873d" '
                   f'font-size="12">{naam}</text>')
    for naam in reeksen:
        # oudere metingen kennen een jonger proefwerk niet (gesprek begon
        # pas bij run 5) — de lijn begint dan gewoon waar de meting begint
        punten = [(X(s), Y(v[naam])) for s, v in curve if naam in v]
        if punten:
            uit.append(_lijn(punten, KLEUREN.get(naam, GRIJS), naam,
                             dik=(naam == "ladder")))
    uit.append("</svg>")
    return "".join(uit)


FAM_KLEUR = {"rekenen": "#5ca8ff", "puzzel": "#b78ae0", "code": "#7fe0c3",
             "geheugen": "#ffb86b", "logica": "#ff8fa3", "volgorde": "#8fd3ff", "tekst": "#e6d37a", "zeggen": "#f5a3ff", "taal": "#a3ffd6", "machine": "#ffd28f", "tellen": "#8fffb0", "antwoord": "#c8b4ff"}


def keuzes_sectie():
    """Haar eigen keuzes (F, 17 aug 2026): het venster telt per blok van 500
    stappen welke familie/diepte zij zelf koos (brein/keuzes-stand.json).
    Hier: het verloop als gestapelde aandelen en de jongste ~500 in cijfers."""
    try:
        with open("/home/arch/amber-werk/brein/keuzes-stand.json") as f:
            k = json.load(f)
    except Exception:
        return ""
    blokken = k.get("blokken") or {}
    if not blokken:
        return ""
    volgorde = sorted(blokken, key=int)
    fams = sorted({f for b in blokken.values() for f in b})
    W, H, L = 900, 160, 60
    n = len(volgorde)
    bw = max(2, (W - L - 20) / n)
    svg = [f'<svg viewBox="0 0 {W} {H + 40}" width="100%" height="{H + 40}">']
    for i, blok in enumerate(volgorde):
        b = blokken[blok]
        tot = sum(sum(d.values()) for d in b.values()) or 1
        y = 10.0
        x = L + i * bw
        for fam in fams:
            aandeel = sum(b.get(fam, {}).values()) / tot
            hh = aandeel * H
            svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw - 1:.1f}" height="{hh:.1f}" '
                       f'fill="{FAM_KLEUR.get(fam, GRIJS)}" opacity=".85"><title>stap {int(blok):,}: '
                       f'{fam} {aandeel:.0%}</title></rect>'.replace(",", "."))
            y += hh
    for i in range(0, n, max(1, n // 8)):
        svg.append(f'<text x="{L + i * bw:.0f}" y="{H + 28}" fill="#9aa7c9" font-size="11">'
                   f'{int(volgorde[i]):,}</text>'.replace(",", "."))
    for j, fam in enumerate(fams):
        svg.append(f'<rect x="{10 + j * 110}" y="{H + 16}" width="10" height="10" fill="{FAM_KLEUR.get(fam, GRIJS)}"/>'
                   f'<text x="{24 + j * 110}" y="{H + 26}" fill="#9aa7c9" font-size="12">{fam}</text>')
    svg.append("</svg>")
    # de jongste ~500 keuzes in cijfers
    laatste, per_diepte, tel = {}, {}, 0
    for blok in reversed(volgorde):
        for fam, d in blokken[blok].items():
            for diepte, aantal in d.items():
                laatste[fam] = laatste.get(fam, 0) + aantal
                per_diepte.setdefault(fam, {})[int(diepte)] = per_diepte.setdefault(fam, {}).get(int(diepte), 0) + aantal
                tel += aantal
        if tel >= 500:
            break
    regels = ""
    for fam in sorted(laatste, key=lambda f: -laatste[f]):
        ds = sorted(per_diepte[fam])
        top = max(per_diepte[fam], key=per_diepte[fam].get)
        regels += (f"<tr><td>{fam}</td><td>{100 * laatste[fam] / max(1, tel):.0f}%</td>"
                   f"<td>{ds[0]}–{ds[-1]}</td><td>{top}</td></tr>")
    return f"""<h2>Haar eigen keuzes (F)</h2>
<p class="stil">Waar haar nieuwsgierigheid heen gaat: per blok van 500 stappen het aandeel
van elke familie in wat zij zélf koos (de stap-regels van haar logboek, geteld door het
venster). Trekken gaat naar verhouding over (familie, diepte): een familie met veel open
dieptes weegt vanzelf zwaarder.</p>
<div class="graf">{"".join(svg)}</div>
<table><tr><th style="text-align:left">familie</th><th>aandeel (jongste {tel})</th>
<th>dieptes</th><th>meest gekozen</th></tr>{regels}</table>
"""


def maak_html(d):
    curve, laatste = d["curve"], d["laatste"]
    nu = time.strftime("%-d %b %Y, %H:%M")
    pct = 100 * d["stap"] // TOTAAL
    scores = curve[-1][1]

    if d["klaar"]:
        status = '<span class="af">definitief — de run is af</span>'
        eind = f"{d['stap']:,}".replace(",", ".") + " stappen voltooid"
    else:
        status = f'<span class="loop">tussenstand — de run loopt ({pct}%)</span>'
        resterend = (TOTAAL - d["stap"]) * (laatste["ms"] if laatste else 800) / 1000
        klaar_om = time.strftime("%H:%M", time.localtime(time.time() + resterend))
        dag = "vandaag" if resterend < 86_400 - 3600 * time.localtime().tm_hour else "morgen"
        eind = f"verwacht klaar {dag} rond {klaar_om}"

    # Het zorgpunt in tekst: grondslag laatste vijf metingen tegen de piek.
    g = [v["grondslag"] for _, v in curve]
    g_nu = sum(g[-5:]) / min(5, len(g))
    g_piek = max(g)
    zorg = ""
    if g_piek - g_nu >= 5:
        zorg = (f'<p class="zorg">⚠ Grondslag staat gemiddeld op {g_nu:.0f}% '
                f'tegen een piek van {g_piek}% — de basis slijt terwijl het '
                f'front rent. Dit is het eerste aandachtspunt voor na de run.</p>')

    # Het groeisignaal van E (15 aug 2026): een los script, hier alleen
    # getoond. Ontbreekt het of struikelt het, dan staat dát er.
    try:
        r = subprocess.run([sys.executable,
                            "/home/arch/amber-werk/fase1/groei-advies.py",
                            "/home/arch/leven.log"],
                           capture_output=True, text=True, timeout=60)
        advies = (r.stdout or r.stderr).strip() or "(geen uitvoer)"
    except Exception as e:                    # noqa: BLE001
        advies = f"groei-advies niet beschikbaar: {e}"

    doorbraak_regels = "".join(
        f"<tr><td>{s:,}</td><td>{fam}</td><td>tot diepte {tot}</td></tr>"
        .replace(",", ".") for s, fam, tot in d["doorbraken"])

    vaste_volgorde = ("ladder", "gesprek", "diepte2", "diepte", "gemengd",
                      "grondslag")
    kaart_namen = ([n for n in vaste_volgorde if n in scores]
                   + sorted(n for n in scores if n not in vaste_volgorde))
    # alle proefwerken die in deze run gemeten zijn, de ladder apart —
    # nieuwe bladen (diepte3, stapel op run 6) doen zo vanzelf mee
    proef_namen = [n for n in kaart_namen if n != "ladder"]
    kaart = "".join(
        f'<div class="vak"><div class="cijfer" '
        f'style="color:{KLEUREN.get(n, GRIJS)}">'
        f'{scores[n]}%</div><div class="naam">{n}</div></div>'
        for n in kaart_namen)

    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{NAAM.capitalize()} — {('eindrapport' if d['klaar'] else 'tussenstand')}</title>
<style>
  body {{ background:#0a1420; color:#cfe0ef; font: 16px/1.55 system-ui,
         sans-serif; max-width: 1000px; margin: 0 auto; padding: 24px; }}
  h1 {{ color:#ffc35c; font-size: 1.6rem; margin-bottom: .2rem; }}
  h2 {{ color:#8fb2d0; font-size: 1.1rem; margin-top: 2rem; }}
  .af   {{ color:#5ad18f; font-weight: 600; }}
  .loop {{ color:#5aa7e8; font-weight: 600; }}
  .stil {{ color:#5a7a96; font-size: .9rem; }}
  .vakken {{ display:flex; gap:12px; flex-wrap:wrap; margin:20px 0; }}
  .vak {{ background:#101e30; border-radius:10px; padding:14px 20px;
          text-align:center; flex:1; min-width:110px; }}
  .cijfer {{ font-size:1.9rem; font-weight:700;
             font-variant-numeric: tabular-nums; }}
  .naam {{ color:#7a9ab8; font-size:.85rem; }}
  .advies {{ background:#151a2a; border-left:4px solid #6f8fd6; padding:10px 14px;
            font-size:13px; white-space:pre-wrap; overflow-x:auto; }}
  .zorg {{ background:#2a1a1a; border-left:4px solid #e87a7a;
           padding:10px 14px; border-radius:6px; }}
  table {{ border-collapse:collapse; font-variant-numeric: tabular-nums; }}
  td {{ padding:4px 18px 4px 0; border-bottom:1px solid #1c3048; }}
  .graf {{ background:#0d1826; border-radius:12px; padding:16px;
           overflow-x:auto; }}
</style></head><body>
<h1>{NAAM.capitalize()} — {f"{TOTAAL:,}".replace(",", ".")} stappen</h1>
<p>{status} &nbsp;·&nbsp; {eind} &nbsp;·&nbsp;
   <span class="stil">bijgewerkt {nu}, ververst elk kwartier</span></p>
<div class="vakken">{kaart}</div>
<h2>De ladder — haar hele wereld, gewogen</h2>
<div class="graf">{grafiek(curve, ["ladder"], d["doorbraken"])}</div>
<p class="stil">De stippellijnen zijn doorbraken: het moment waarop ze zelf
een diepte openmaakte (r = rekenen, c = code, p = puzzel, g = geheugen, l = logica, v = volgorde, t = tekst).</p>
<h2>De bevroren proefwerken ({len(proef_namen)})</h2>
<div class="graf">{grafiek(curve, proef_namen, hoog=340)}</div>
<p class="stil">Bevroren op 9 aug 2026 — elke meting is exact dezelfde
opgavenlijst, dus deze lijnen zijn over de hele run vergelijkbaar.
Ter vergelijking: run 2 eindigde op ladder 72%.</p>
{zorg}
<h2>Groei-advies (E)</h2>
<pre class="advies">{advies}</pre>
<p class="stil">Vlak + meters niet vol + wereld dicht → "overweeg een laag";
anders wat er wél speelt. Een voorstel, geen automatisme.</p>
{keuzes_sectie()}
<h2>Doorbraken</h2>
<table><tr><th style="text-align:left">stap</th>
<th style="text-align:left">familie</th><th></th></tr>{doorbraak_regels}</table>
<h2>Bedrijf</h2>
<p>Herstarts zichtbaar in het log: {d["herstarts"]} — incidenten én bewuste
herstarts voor hek-wijzigingen samen · tempo nu:
{laatste["ms"] if laatste else "?"} ms per stap · hek: {HEK} (gemeten
grenzen van het venster van {VENSTER} tekens){VORM_TEKST}.</p>
</body></html>"""


def hoofd():
    d = ontleed(haal_log())
    html = maak_html(d)
    for pad in (DOEL, DOEL_INDEX):
        with open(pad + ".deel", "w") as f:
            f.write(html)
        import os
        os.replace(pad + ".deel", pad)
    print(f"rapport geschreven: stap {d['stap']}, "
          f"{'definitief' if d['klaar'] else 'tussenstand'}")


if __name__ == "__main__":
    sys.exit(hoofd())
