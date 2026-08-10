"""
De eindrapport-maker van run 3.

Draait op de DL380, elk kwartier (amber-rapport.timer). Haalt het levenslog
van de X399, ontleedt het, en schrijft één zelfstandig HTML-bestand naar
/home/arch/rapport/ — zolang de run loopt als tussenstand, en zodra stap
170.000 binnen is (of de dienst gestopt is op het eindpunt) als definitief
eindrapport. Het rapport hoeft dus nooit "gemaakt" te worden: het staat er
al op het moment dat iemand komt kijken.

Alleen standaardbibliotheek. Het log is de enige waarheid; is de X399
onbereikbaar, dan blijft het vorige rapport gewoon staan.
"""

import re
import subprocess
import sys
import time

X399 = "arch@192.168.1.170"
GEHEIM_PAD = "/home/arch/.amber-geheim"
DOEL = "/home/arch/rapport/run3.html"
DOEL_INDEX = "/home/arch/rapport/index.html"
TOTAAL = 170_000

KLEUREN = {  # op donkerblauw; identiteit zit ook in de eindlabels, niet
    "ladder": "#ffc35c",       # alleen in kleur
    "diepte2": "#5ad18f",
    "diepte": "#5aa7e8",
    "gemengd": "#b58ae0",
    "grondslag": "#e87a7a",
}


def haal_log():
    geheim = open(GEHEIM_PAD).read().strip()
    uit = subprocess.run(
        ["sshpass", "-p", geheim, "ssh", "-o", "ConnectTimeout=10",
         "-o", "StrictHostKeyChecking=no", X399, "cat ~/leven.log"],
        capture_output=True, text=True, timeout=60)
    if uit.returncode != 0:
        raise RuntimeError(f"log niet op te halen: {uit.stderr[:200]}")
    return uit.stdout


def ontleed(log):
    """Alles wat het rapport nodig heeft, uit het log.

    Het log loopt door over runs en herstarts heen. De run-3-regels zijn de
    langste staart waarin de proefwerkstappen oplopen — dezelfde truc als in
    server.py. Herstartregels met stap 0 doen niet mee aan de staart maar
    tellen wél als herstart.
    """
    regels = log.splitlines()
    proef = []          # (regelnr, stap, {naam: score})
    p_proef = re.compile(
        r"stap\s+(\d+) \| diepte\s+(\d+)%\s+diepte2\s+(\d+)%\s+gemengd\s+(\d+)%"
        r"\s+grondslag\s+(\d+)%\s+ladder\s+(\d+)%")
    for i, r in enumerate(regels):
        m = p_proef.search(r)
        if m:
            stap = int(m.group(1))
            proef.append((i, stap, {
                "diepte": int(m.group(2)), "diepte2": int(m.group(3)),
                "gemengd": int(m.group(4)), "grondslag": int(m.group(5)),
                "ladder": int(m.group(6))}))

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
    for naam in reeksen:
        punten = [(X(s), Y(v[naam])) for s, v in curve]
        uit.append(_lijn(punten, KLEUREN[naam], naam, dik=(naam == "ladder")))
    uit.append("</svg>")
    return "".join(uit)


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

    doorbraak_regels = "".join(
        f"<tr><td>{s:,}</td><td>{fam}</td><td>tot diepte {tot}</td></tr>"
        .replace(",", ".") for s, fam, tot in d["doorbraken"])

    kaart = "".join(
        f'<div class="vak"><div class="cijfer" style="color:{KLEUREN[n]}">'
        f'{scores[n]}%</div><div class="naam">{n}</div></div>'
        for n in ("ladder", "diepte2", "diepte", "gemengd", "grondslag"))

    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Run 3 — {('eindrapport' if d['klaar'] else 'tussenstand')}</title>
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
  .zorg {{ background:#2a1a1a; border-left:4px solid #e87a7a;
           padding:10px 14px; border-radius:6px; }}
  table {{ border-collapse:collapse; font-variant-numeric: tabular-nums; }}
  td {{ padding:4px 18px 4px 0; border-bottom:1px solid #1c3048; }}
  .graf {{ background:#0d1826; border-radius:12px; padding:16px;
           overflow-x:auto; }}
</style></head><body>
<h1>Run 3 — 170.000 stappen</h1>
<p>{status} &nbsp;·&nbsp; {eind} &nbsp;·&nbsp;
   <span class="stil">bijgewerkt {nu}, ververst elk kwartier</span></p>
<div class="vakken">{kaart}</div>
<h2>De ladder — haar hele wereld, gewogen</h2>
<div class="graf">{grafiek(curve, ["ladder"], d["doorbraken"])}</div>
<p class="stil">De stippellijnen zijn doorbraken: het moment waarop ze zelf
een diepte openmaakte (r = rekenen, c = code, p = puzzel).</p>
<h2>De vier bevroren proefwerken</h2>
<div class="graf">{grafiek(curve, ["diepte2", "diepte", "gemengd", "grondslag"], hoog=340)}</div>
<p class="stil">Bevroren op 9 aug 2026 — elke meting is exact dezelfde
opgavenlijst, dus deze lijnen zijn over de hele run vergelijkbaar.
Ter vergelijking: run 2 eindigde op ladder 72%.</p>
{zorg}
<h2>Doorbraken</h2>
<table><tr><th style="text-align:left">stap</th>
<th style="text-align:left">familie</th><th></th></tr>{doorbraak_regels}</table>
<h2>Bedrijf</h2>
<p>Herstarts zichtbaar in het log: {d["herstarts"]} — incidenten én bewuste
herstarts voor hek-wijzigingen samen · tempo nu:
{laatste["ms"] if laatste else "?"} ms per stap · hek: rekenen 17, code 8,
puzzel 5 (gemeten grenzen van het venster van 512 tekens).</p>
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
