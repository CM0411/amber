"""Bouwt index-v2.html: de nieuwe app (v2-kop.html) met het weefsel-tekenwerk
uit het oude venster, opnieuw afgesteld.
"""
import pathlib

HIER = pathlib.Path(__file__).parent
oud = (HIER / "index.html").read_text()
js = oud[oud.index("<script>") + len("<script>"):oud.rindex("</script>")]

# blok A: staat, plaats/kromming, maat, bouwWeefsel, bouwNamen
a0 = js.index('const doek = document.getElementById("doek");')
a1 = js.index("bouwNamen();\n", js.index("function bouwNamen()")) + len("bouwNamen();\n")
A = js[a0:a1]
# blok B: teken() tot het eind
b0 = js.index("function teken(t) {")
B = js[b0:].rstrip()

def patch(blok, oud_stuk, nieuw_stuk):
    assert blok.count(oud_stuk) == 1, oud_stuk[:70]
    return blok.replace(oud_stuk, nieuw_stuk)

# --- A: het paneel bepaalt de maat, niet het venster; nieuwe kleuren -------
A = patch(A, '''  B = doek.width = innerWidth * DPR;
  H = innerHeight * DPR;                       // de maat van de tekening
  doek.height = Math.round(H * BAND);          // getoond: de bovenste band''',
'''  // Het paneel bepaalt de maat (24 aug 2026): het weefsel zit in zijn
  // eigen vak en schaalt mee. De tekening rekent nog in de hoogte H,
  // waarvan de bovenste BAND zichtbaar is -- precies de band met namen.
  if (!doek.clientWidth) return;               // tab niet in beeld
  B = doek.width = doek.clientWidth * DPR;
  H = doek.clientHeight * DPR / BAND;
  doek.height = Math.round(doek.clientHeight * DPR);''')
A = patch(A, '''  g.addColorStop(0, "#080b1e"); g.addColorStop(.5, "#0c1230");
  g.addColorStop(1, "#070a1a");''',
'''  g.addColorStop(0, "#0A0E1C"); g.addColorStop(.55, "#0D1326");
  g.addColorStop(1, "#080B18");''')
A = patch(A, "      paren = paren.slice(0, 240);", "      paren = paren.slice(0, 320);")
A = patch(A, '''      q.strokeStyle = plus
        ? `rgba(105,225,150,${(0.05 + w * 0.30).toFixed(3)})`
        : `rgba(255,115,85,${(0.05 + w * 0.30).toFixed(3)})`;
      q.lineWidth = Math.max(0.6, Math.min(B, H) * 0.0007);''',
'''      // mint voor plus, koraal voor min; dikte en helderheid naar gewicht
      q.strokeStyle = plus
        ? `rgba(127,224,195,${(0.04 + w * 0.34).toFixed(3)})`
        : `rgba(255,154,122,${(0.04 + w * 0.34).toFixed(3)})`;
      q.lineWidth = Math.max(0.5, Math.min(B, H) * (0.0004 + 0.0012 * w));''')
A = patch(A, 'addEventListener("resize", maat);',
'''addEventListener("resize", maat);
if (window.ResizeObserver) new ResizeObserver(() => maat()).observe(document.getElementById("weefsel"));''')

# --- B: laagnamen die elkaar nooit raken; rustiger bollen ------------------
B = patch(B, '''  const fs = Math.max(7, Math.min(mn * 0.0102, kolAfstand / 6.2));
  ctx.font = `${fs}px ui-monospace, Consolas, monospace`;
  for (let k = 0; k < KOL.length; k++) {
    const [x] = plaats(k, 0);''',
'''  // Namen alleen waar ze passen (24 aug 2026): wordt het krap, dan om de
  // andere laag, en nooit kleiner dan leesbaar -- liever minder dan over
  // elkaar. Invoer en uitvoer staan er altijd.
  const fs = Math.max(9.5 * DPR, Math.min(mn * 0.0105, kolAfstand / 5.6));
  const om = Math.max(1, Math.ceil(fs * 7.2 / kolAfstand));
  ctx.font = `500 ${fs}px "JetBrains Mono", ui-monospace, Consolas, monospace`;
  for (let k = 0; k < KOL.length; k++) {
    if (om > 1 && k % om !== 0 && k !== KOL.length - 1) continue;
    const [x] = plaats(k, 0);''')
B = patch(B, '''    ctx.fillStyle = "rgba(225,235,255,0.85)";
    ctx.fillText(NAMEN[k][0], lx, y);
    ctx.fillStyle = "rgba(255,140,90,0.8)";
    ctx.fillText(NAMEN[k][1], lx, y + fs * 1.35);''',
'''    ctx.fillStyle = "rgba(234,238,247,0.9)";
    ctx.fillText(NAMEN[k][0], lx, y);
    if (om === 1 || k === 0 || k === KOL.length - 1) {
      ctx.fillStyle = "rgba(142,153,179,0.95)";
      ctx.fillText(NAMEN[k][1], lx, y + fs * 1.4);
    }''')
B = patch(B, '''      ctx.fillStyle = `rgba(${205 + 50 * gl | 0},${220 + 35 * gl | 0},255,${(0.5 + 0.5 * gl).toFixed(2)})`;''',
'''      ctx.fillStyle = `rgba(${190 + 60 * gl | 0},${205 + 45 * gl | 0},${235 + 20 * gl | 0},${(0.42 + 0.58 * gl).toFixed(2)})`;''')

kop = (HIER / "v2-kop.html").read_text()
iris = (HIER / "v2-microscoop.js").read_text()
uit = kop.replace("/*__WEEFSEL_A__*/", iris).replace("/*__WEEFSEL_B__*/", "")
# het blad-wisselen moet het weefsel opnieuw meten als het weer in beeld komt
uit = uit.replace('  window.scrollTo({top: 0});\n}', '  window.scrollTo({top: 0});\n  if (naam === "overzicht" && typeof maat === "function") setTimeout(maat, 0);\n}')
(HIER / "index-v2.html").write_text(uit)
print(f"index-v2.html: {len(uit)} tekens (weefsel A {len(A)}, B {len(B)})")
