/* ======================================================================
   De Sterrenwacht — Claudes ontwerp, van de grond af (24 aug 2026, Cley:
   "begin vanaf nul tot je eigen futuristische design").

   Geen website met bladen. Eén scherm. Haar brein in het midden, als
   cellen en vezels (Cleys derde afbeelding, 24 aug laat: "dit is hem"):
   elke laag een ronde cel, haar 32 groepen van 12 kanalen als punten op
   de rand; tussen de cellen de sterkste echte gewichten als vezels die
   om de cellen heen krullen; om elke cel bogen voor de groepen die in
   deze gedachte samen vuren. Zwart, wit, cyaan. Alleen de vezel waar
   iets doorheen gaat licht op; niets flitst. Elke knoop is echt: een groep van 12 kanalen
   uit haar residustroom (32 per laag, 20 lagen, plus de 32 van de
   inbedding en de ene knoop van de uitvoer). Elke lijn is echt: tussen
   twee lagen de sterkste gewichten van groep naar groep (bleek plus,
   koraal min), binnen een laag de groepen die in deze gedachte samen
   vuren (correlatie over de doorgangen). Het licht is haar gemeten
   activiteit per geschreven teken; de felste knopen krijgen een stille
   gloed. Draaien met de muis, klik op een knoop en de microscoop van die
   laag gaat open (daar wél elk kanaal apart). Niets flitst; de ruimte
   draait langzaam als je even niets doet.
   ====================================================================== */
const doek = document.getElementById("doek");
const ctx = doek.getContext("2d");
const DPR = Math.min(devicePixelRatio || 1, 2);
let B = 1, H = 1;
let KOL = [32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 1];
let NAMEN = [];
let stand = null, wachtrij = [], rijNu = null;
let kolMax = KOL.map(() => 0.0001);
let bedrading = null, bedradingUit = null, weefsel = [];
let antwoordDoel = "", antwoordNu = 0, laatstTonen = 0;
let rijen = [];                         // doorgangen van deze gedachte: rijen[j][k] = 32 groepen
let speelStart = 0, klaarSinds = 0, muis = null, vast = null;
const TEKEN_S = 0.7, VEEG = 0.5;
let laagnamen = {};
let spec = {koppen: 6, verborgen: 1536, breedte: 384};
let zoom = {laag: null, t: 0, doel: 0};
let LIVE = false;                        // live: het beeld volgt de laatste doorgang uit live.json, niets wordt afgespeeld
const RUSTIG = matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ---- de fijne meting: per kanaal, per kop, per eenheid ---- */
let fijn = null, fijnTijd = 0, fijnBezig = false;
async function haalFijn(tijd) {
  if (tijd === fijnTijd || fijnBezig) return;
  fijnBezig = true;
  try {
    const r = await fetch("/rapport/fijn.json", {cache: "no-store"});
    const f = await r.json();
    if (f && f.kanaal && f.tijd === tijd) { fijn = f; fijnTijd = tijd; }
  } catch (e) {} finally { fijnBezig = false; }
}
const fijnPast = () => fijn && stand && fijn.tijd === stand.tijd;
function fijnKanaal(j, k) { return (fijnPast() && k >= 1 && k <= fijn.lagen && fijn.kanaal[j]) ? fijn.kanaal[j][k - 1] : null; }
function fijnKop(j, k) { return (fijnPast() && k >= 1 && k <= fijn.lagen && fijn.kop && fijn.kop[j]) ? fijn.kop[j][k - 1] : null; }
function fijnFfGroep(j, k) { return (fijnPast() && k >= 1 && k <= fijn.lagen && fijn.ff_groep && fijn.ff_groep[j]) ? fijn.ff_groep[j][k - 1] : null; }
function fijnFfEenheid(k) { return (fijnPast() && k >= 1 && k <= fijn.lagen && fijn.ff_eenheid) ? fijn.ff_eenheid[k - 1] : null; }
const FAMILIEKLEUR = {rekenen: "#6FB5FF", puzzel: "#B78AE0", code: "#7FE0C3", geheugen: "#FFB86B", logica: "#FF8FA3",
                      volgorde: "#8FD3FF", tekst: "#E6D37A", zeggen: "#F0A8FF", taal: "#A3FFD6", machine: "#FFD28F",
                      tellen: "#C4B5FD", antwoord: "#FDA4AF", antwoordlaag: "#FDA4AF", gesprek: "#F0A8FF", gemengd: "#8E99B3"};
const kleurVan = b => FAMILIEKLEUR[b] || (b === "stil" ? "#5C6781" : "#8E99B3");

/* ---- maat: het doek is het hele scherm; de ruimte zit in het vrije midden ---- */
const P = {fs: 12, boven: 0, vrijX: 0, vrijY: 0, vrijB: 1, vrijH: 1};
function maat() {
  if (!doek.clientWidth) return;
  B = doek.width = Math.round(doek.clientWidth * DPR);
  H = doek.height = Math.round(doek.clientHeight * DPR);
  P.fs = Math.max(10, Math.min(13, B / 115)) * DPR;
  const r = doek.getBoundingClientRect();
  const vrij = document.getElementById("vrij").getBoundingClientRect();
  P.boven = Math.max(0, (vrij.top - r.top)) * DPR;
  P.vrijX = (vrij.left - r.left) * DPR; P.vrijY = (vrij.top - r.top) * DPR;
  P.vrijB = Math.max(1, vrij.width * DPR); P.vrijH = Math.max(1, vrij.height * DPR);
  vuil = true;
}
addEventListener("resize", maat);
if (window.ResizeObserver) new ResizeObserver(() => maat()).observe(document.getElementById("vrij"));

/* ---- de vorm: cellen, vezels en bogen ---- */
function rnd(seed) {                      // vaste toevalsgetallen: dezelfde cel staat altijd op dezelfde plek
  let t = (seed | 0) + 0x6D2B79F5; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61);
  return ((t ^ t >>> 14) >>> 0) / 4294967296;
}
let vorm = [], glad = [];                // per station: {k, x, y, r, fase, n, soort, pt: [[x,y]] (groepen op de rand)}
let lijnen = [], samen = [];             // de bedrading tussen de lagen; wie samen vuurt binnen een laag
function bouwVorm() {
  const n = KOL.length, lagen = n - 2;
  // de sterkte van de bedrading per laag bepaalt de maat van de cel (vast, uit de gewichten)
  const kracht = [];
  for (let k = 0; k < n; k++) {
    let som = 0;
    const M = (k >= 1 && k <= lagen && bedrading) ? bedrading[k] : null;
    if (M) { const alle = []; for (const rij of M) for (const w of (rij || [])) alle.push(Math.abs(w)); alle.sort((p, q) => q - p); for (const w of alle.slice(0, 40)) som += w; }
    kracht.push(som);
  }
  const kmax = Math.max(0.0001, ...kracht);
  vorm = [];
  for (let k = 0; k < n; k++) {
    const st = {k, n: KOL[k], soort: KOL[k] === 1 ? "uit" : (k === 0 ? "in" : "laag"), fase: rnd(k * 53 + 7) * 2 * Math.PI, pt: []};
    if (st.soort === "laag") {
      const t = (k - 1) / Math.max(1, lagen - 1);
      st.x = -4.4 + 8.8 * t; st.y = 1.9 * Math.sin(t * Math.PI * 1.7 + 0.5) + (rnd(k * 53 + 1) - 0.5) * 2.4;
      st.r = 0.32 + 1.0 * (bedrading ? Math.pow(kracht[k] / kmax, 1.6) : 0.6);
    } else if (st.soort === "in") { st.x = -6.6; st.y = 0.6; st.r = 0.9; }
    else { st.x = 6.6; st.y = -0.4; st.r = 0.26; }
    vorm.push(st);
  }
  // cellen die elkaar raken zachtjes uit elkaar duwen (alleen de lagen)
  for (let it = 0; it < 80; it++) for (let i = 1; i <= lagen; i++) for (let j = i + 1; j <= lagen; j++) {
    const a = vorm[i], b = vorm[j], dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 0.001, min = a.r + b.r + 0.55;
    if (d < min) { const p = (min - d) / 2, ux = dx / d, uy = dy / d; a.x -= ux * p; a.y -= uy * p; b.x += ux * p; b.y += uy * p; }
  }
  // de groepen: punten op de rand (lagen), een wolk (inbedding) of de ene knoop (uitvoer)
  for (const st of vorm) {
    st.pt = [];
    for (let i = 0; i < st.n; i++) {
      if (st.soort === "laag") { const a = st.fase + i / st.n * 2 * Math.PI; st.pt.push([st.x + Math.cos(a) * st.r, st.y + Math.sin(a) * st.r]); }
      else if (st.soort === "in") { const r = Math.sqrt(rnd(i * 17 + 3)) * st.r, a = rnd(i * 17 + 4) * 2 * Math.PI; st.pt.push([st.x + Math.cos(a) * r, st.y + Math.sin(a) * r * 0.8]); }
      else st.pt.push([st.x, st.y]);
    }
  }
  glad = vorm.map(st => new Float32Array(st.n));
  // de bedrading: per overgang de sterkste gewichten van groep naar groep, naar het eigen maximum
  lijnen = [];
  for (let k = 0; k < n - 1; k++) {
    let wmax = 0.0001;
    const M = (k < n - 2 && bedrading) ? bedrading[k] : null, U = (k === n - 2) ? bedradingUit : null;
    const alle = [];
    if (M) for (let d = 0; d < M.length; d++) for (let b = 0; b < (M[d] || []).length; b++) alle.push([Math.abs(M[d][b]), M[d][b], b, d]);
    else if (U) for (let b = 0; b < U.length; b++) alle.push([Math.abs(U[b]), U[b], b, 0]);
    alle.sort((p, q) => q[0] - p[0]);
    const top = alle.slice(0, U ? 32 : 40);
    for (const [, w] of top) wmax = Math.max(wmax, Math.abs(w));
    for (const [, w, b, d] of top) lijnen.push({k, w, b, d, a: Math.abs(w) / wmax});
  }
  vuil = true;
}
function bouwSamen() {
  // binnen een laag: welke groepen bewegen in deze gedachte mee met elkaar (correlatie over de doorgangen);
  // per groep de twee sterkste partners -- dat zijn de bogen om de cel
  samen = [];
  if (rijen.length < 4) return;
  const reeksRijen = rijen.slice(-96);       // live: de laatste 96 doorgangen (samen vuren is iets van nu)
  for (let k = 0; k < KOL.length; k++) {
    const G = KOL[k]; if (G < 3) continue;
    const reeks = [];
    for (let g = 0; g < G; g++) {
      const v = reeksRijen.map(r => (r[k] || [])[g] || 0), m = v.reduce((p, q) => p + q, 0) / v.length;
      const c = v.map(x => x - m), norm = Math.sqrt(c.reduce((p, q) => p + q * q, 0)) || 1;
      reeks.push(c.map(x => x / norm));
    }
    const gezien = new Set();
    for (let g = 0; g < G; g++) {
      const cor = [];
      for (let h = 0; h < G; h++) { if (h === g) continue; let d = 0; for (let j = 0; j < reeks[g].length; j++) d += reeks[g][j] * reeks[h][j]; cor.push([d, h]); }
      cor.sort((p, q) => q[0] - p[0]);
      for (const [c, h] of cor.slice(0, 2)) { const id = g < h ? g * G + h : h * G + g; if (c > 0.35 && !gezien.has(id)) { gezien.add(id); samen.push({k, a: g, b: h, c}); } }
    }
  }
  vuil = true;
}
function bouwWeefsel() { bouwVorm(); weefsel = [true]; }
function bouwNamen() {
  NAMEN = [["invoer", "inbedding"]];
  for (let i = 1; i < KOL.length - 1; i++) NAMEN.push(["laag " + i, laagnamen[i] || "GELU"]);
  NAMEN.push(["uitvoer", "zekerheid"]);
  if (stand && stand.run && stand.run.config) {
    const c = stand.run.config;
    spec = {koppen: c.koppen || 6, verborgen: c.verborgen || 1536, breedte: 384};
  }
  bouwVorm(); maat();
  if (typeof bouwRail === "function") bouwRail();
}
function nieuweGedachte(t) {
  rijen = wachtrij.slice(); wachtrij = []; rijNu = rijen.length ? rijen[0] : null;
  speelStart = t; klaarSinds = 0; vast = null;
  kolMax = KOL.map((n, k) => { let m = 0.0001; for (const r of rijen) for (const v of (r[k] || [])) m = Math.max(m, v); return m; });
  bouwSamen();
  if (typeof bouwGedachte === "function") bouwGedachte();
}

/* ---- het beeld: plat, passend in het vrije vak; slepen verschuift, scrollen zoomt ---- */
const cam = {zoom: 1, dx: 0, dy: 0};
let vuil = true, S = 100, CX = 0, CY = 0, laatstBediend = 0;
let proj = [];                           // per station: {k, cx, cy, r, pt: Float32Array}
let vezels = [], bogen = [];             // de vaste tekening: per vezel/boog de schermpunten
const basisDoek = document.createElement("canvas");   // alles wat stil is, één keer getekend; per beeld alleen gekopieerd
let basisKlaar = false;
function projecteer() {
  let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
  for (const st of vorm) { x0 = Math.min(x0, st.x - st.r); x1 = Math.max(x1, st.x + st.r); y0 = Math.min(y0, st.y - st.r); y1 = Math.max(y1, st.y + st.r); }
  S = Math.min(P.vrijB / (x1 - x0 + 1.2), P.vrijH / (y1 - y0 + 1.0)) * cam.zoom;
  CX = P.vrijX + P.vrijB / 2 - (x0 + x1) / 2 * S + cam.dx; CY = P.vrijY + P.vrijH / 2 + (y0 + y1) / 2 * S + cam.dy;
  const sx = x => CX + x * S, sy = y => CY - y * S;
  proj = vorm.map(st => { const pt = new Float32Array(st.n * 2); st.pt.forEach(([x, y], i) => { pt[2 * i] = sx(x); pt[2 * i + 1] = sy(y); }); return {k: st.k, cx: sx(st.x), cy: sy(st.y), r: st.r * S, pt}; });
  // de vezels: van groep b op cel k naar groep d op cel k+1, rakend aan beide cellen, in drie strengen
  vezels = [];
  for (const l of lijnen) {
    const A = vorm[l.k], Bc = vorm[l.k + 1]; if (!A || !Bc) continue;
    const strengen = [];
    for (const off of [-0.045, 0, 0.045]) {
      const p = rand(A, l.b, off), q = rand(Bc, l.d, off);
      const dx = q[0] - p[0], dy = q[1] - p[1], len = Math.hypot(dx, dy) || 0.001;
      const tp = raak(A, p, dx, dy), tq = raak(Bc, q, -dx, -dy), d1 = Math.min(1.6, 0.45 * len);
      strengen.push([sx(p[0]), sy(p[1]), sx(p[0] + tp[0] * d1), sy(p[1] + tp[1] * d1), sx(q[0] + tq[0] * d1), sy(q[1] + tq[1] * d1), sx(q[0]), sy(q[1])]);
    }
    vezels.push({l, strengen});
  }
  // de bogen: om de cel heen, de korte kant op, in twee strengen net buiten de rand
  bogen = [];
  for (const b of samen) {
    const st = vorm[b.k]; if (!st || st.soort !== "laag") continue;
    let a1 = st.fase + b.a / st.n * 2 * Math.PI, a2 = st.fase + b.b / st.n * 2 * Math.PI;
    let d = a2 - a1; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI;
    const strengen = [];
    for (const off of [0.035, 0.075]) strengen.push([sx(st.x), sy(st.y), (st.r + off) * S, -a1, -(a1 + d), d < 0]);
    bogen.push({b, strengen});
  }
  // alles wat stil is: één keer op een eigen doek (de vezels zijn met duizenden; per beeld alleen kopiëren)
  basisDoek.width = B; basisDoek.height = H;
  const q = basisDoek.getContext("2d");
  q.clearRect(0, 0, B, H); q.lineCap = "round"; q.lineJoin = "round";
  q.lineWidth = DPR * 0.55;
  for (const teken of [1, -1]) {                      // plus wit, min grijsblauw (streepjes tekenen te zwaar)
    q.strokeStyle = teken > 0 ? "rgba(255,255,255,0.035)" : "rgba(150,190,205,0.03)";
    q.beginPath();
    for (const v of vezels) { if ((v.l.w >= 0) !== (teken > 0)) continue; for (const s of v.strengen) { q.moveTo(s[0], s[1]); q.bezierCurveTo(s[2], s[3], s[4], s[5], s[6], s[7]); } }
    q.stroke();
  }
  q.strokeStyle = "rgba(255,255,255,0.035)";
  q.beginPath();
  for (const b of bogen) for (const s of b.strengen) { q.moveTo(s[0] + Math.cos(s[3]) * s[2], s[1] + Math.sin(s[3]) * s[2]); q.arc(s[0], s[1], s[2], s[3], s[4], s[5]); }
  q.stroke();
  basisKlaar = true;
  vuil = false;
}
function rand(st, i, off) {              // een groep op de rand van een cel (met een kleine hoekverschuiving voor de strengen)
  if (st.soort !== "laag") return st.pt[i] || [st.x, st.y];
  const a = st.fase + i / st.n * 2 * Math.PI + off;
  return [st.x + Math.cos(a) * st.r, st.y + Math.sin(a) * st.r];
}
function raak(st, p, dx, dy) {           // de raaklijn aan de cel in p, de kant op waar de andere cel ligt
  if (st.soort !== "laag") { const len = Math.hypot(dx, dy) || 1; return [dx / len * 0.6, dy / len * 0.6]; }
  const rx = p[0] - st.x, ry = p[1] - st.y, len = Math.hypot(rx, ry) || 1;
  let tx = -ry / len, ty = rx / len;
  if (tx * dx + ty * dy < 0) { tx = -tx; ty = -ty; }
  return [tx, ty];
}

/* ---- bediening: verschuiven, zoomen, aanwijzen, klikken ---- */
let sleep = null, hover = {station: null, kanaal: null};
function schermXY(e) { const r = doek.getBoundingClientRect(); const p = e.touches ? e.touches[0] : e; return {x: (p.clientX - r.left) * DPR, y: (p.clientY - r.top) * DPR}; }
doek.addEventListener("pointerdown", e => { if (e.button !== 0 && e.pointerType === "mouse") return; sleep = {x: e.clientX, y: e.clientY, dx: cam.dx, dy: cam.dy, bewogen: false}; doek.setPointerCapture(e.pointerId); laatstBediend = performance.now(); });
doek.addEventListener("pointermove", e => {
  muis = schermXY(e);
  if (sleep) {
    const dx = e.clientX - sleep.x, dy = e.clientY - sleep.y;
    if (Math.hypot(dx, dy) > 4) sleep.bewogen = true;
    if (sleep.bewogen && zoom.t < 0.5) { cam.dx = sleep.dx + dx * DPR; cam.dy = sleep.dy + dy * DPR; vuil = true; }
    laatstBediend = performance.now();
  }
});
doek.addEventListener("pointerup", e => {
  const s = sleep; sleep = null;
  if (!s || s.bewogen) return;
  if (zoom.t < 0.5) { if (hover.station !== null) openLaag(hover.station); }
  else { const p = schermXY(e); if (p.y - P.boven < P.fs * 3.2 && p.x < P.fs * 9) sluit(); }
});
doek.addEventListener("pointercancel", () => { sleep = null; });
doek.addEventListener("pointerleave", () => { muis = null; hover = {station: null, kanaal: null}; });
doek.addEventListener("wheel", e => { if (zoom.t > 0.5) return; e.preventDefault(); cam.zoom = Math.max(0.6, Math.min(3, cam.zoom * Math.exp(-e.deltaY * 0.0012))); vuil = true; laatstBediend = performance.now(); }, {passive: false});
function openLaag(k) { if (k === null || k < 0 || k >= KOL.length) return; zoom.laag = k; zoom.doel = 1; document.body.classList.add("laag-open"); if (typeof toonRail === "function") toonRail(); }
function sluit() { zoom.doel = 0; document.body.classList.remove("laag-open"); if (typeof toonRail === "function") toonRail(); }
addEventListener("keydown", e => {
  if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
  if (e.key === "Escape" && zoom.doel) { sluit(); e.preventDefault(); return; }
  if (zoom.t > 0.5 && zoom.laag !== null) {
    if (e.key === "ArrowRight") { openLaag(Math.min(KOL.length - 1, zoom.laag + 1)); e.preventDefault(); }
    if (e.key === "ArrowLeft") { openLaag(Math.max(0, zoom.laag - 1)); e.preventDefault(); }
  }
});
{ const mm = location.hash.match(/laag=(\d+)/); if (mm) { zoom.laag = +mm[1]; zoom.doel = 1; document.body.classList.add("laag-open"); } }
function zoekHover() {
  hover = {station: null, kanaal: null};
  if (!muis || zoom.t > 0.5 || sleep) return;
  let best = null, bd = 1e18;
  for (const p of proj) { const d = Math.hypot(p.cx - muis.x, p.cy - muis.y); if (d < Math.max(p.r * 1.25, 14 * DPR) && d < bd) { bd = d; best = p.k; } }
  hover.station = best;
}

/* ---- helpers ---- */
function rondRect(q, x, y, w, h, r) { q.beginPath(); q.moveTo(x + r, y); q.arcTo(x + w, y, x + w, y + h, r); q.arcTo(x + w, y + h, x, y + h, r); q.arcTo(x, y + h, x, y, r); q.arcTo(x, y, x + w, y, r); q.closePath(); }
function warm(v) {                       // gewicht -> kleur (de microscoop): cyaan plus, koraal min
  const a = Math.min(1, Math.abs(v));
  return v >= 0 ? `rgba(63,208,224,${(0.08 + 0.92 * a).toFixed(3)})` : `rgba(255,138,112,${(0.08 + 0.92 * a).toFixed(3)})`;
}
function activiteitVan(j, k, i) {         // een groep in doorgang j: 0..1 ten opzichte van het maximum van die laag in deze gedachte
  const rij = rijen[j]; if (!rij) return 0;
  return Math.min(1, ((rij[k] || [])[i] || 0) / kolMax[k]);
}
const CYAAN = "63,208,224";

/* ---- de ruimte: elk beeld ---- */
function tekenRuimte(t, j, veeg, alpha) {
  if (vuil || !proj.length) projecteer();
  ctx.globalAlpha = alpha;
  const rij = (j >= 0 && rijen[j]) ? rijen[j] : null, n = KOL.length, fs = P.fs;
  // elke groep glijdt elk beeld een stukje naar zijn waarde van nu: nooit een sprong, nooit een veeg
  for (let k = 0; k < n; k++) { const g = glad[k]; if (!g) continue; for (let i = 0; i < g.length; i++) { const doel = rij ? activiteitVan(j, k, i) : 0; g[i] += (doel - g[i]) * 0.09; } }
  // de stroom door een draadje: wortel van het product van de activiteit aan beide kanten; onder 0,3 uit
  const stroom = (k1, i1, k2, i2) => { const f = Math.sqrt(Math.max(0, (glad[k1] ? glad[k1][i1] : 0) * (glad[k2] ? glad[k2][i2] : 0))); return Math.max(0, (f - 0.3) / 0.7); };
  // haar naam, groot en hol, als watermerk (tekening)
  ctx.save(); ctx.font = `800 ${Math.round(P.vrijH * 0.34)}px Syne, "Atkinson Hyperlegible", sans-serif`; ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
  ctx.strokeStyle = "rgba(255,255,255,0.045)"; ctx.lineWidth = DPR; ctx.strokeText("AMBER", P.vrijX + fs * 0.5, P.vrijY + P.vrijH - fs * 0.6); ctx.restore();
  // alles wat stil is: de vaste laag
  if (basisKlaar) ctx.drawImage(basisDoek, 0, 0);
  ctx.lineCap = "round"; ctx.lineJoin = "round";
  // de vezels waar iets doorheen gaat: van een actieve groep naar een actieve groep
  for (const v of vezels) {
    const l = v.l, f = stroom(l.k, l.b, l.k + 1, l.d) * (0.5 + 0.5 * l.a);
    if (f < 0.04) continue;
    ctx.strokeStyle = l.w >= 0 ? `rgba(255,255,255,${(0.9 * f).toFixed(3)})` : `rgba(160,205,220,${(0.9 * f).toFixed(3)})`; ctx.lineWidth = DPR * (0.6 + 1.3 * f);
    ctx.beginPath(); for (const s of v.strengen) { ctx.moveTo(s[0], s[1]); ctx.bezierCurveTo(s[2], s[3], s[4], s[5], s[6], s[7]); } ctx.stroke();
  }
  // de bogen waar iets doorheen gaat: twee groepen van dezelfde cel, allebei actief
  for (const b of bogen) {
    const f = stroom(b.b.k, b.b.a, b.b.k, b.b.b) * b.b.c;
    if (f < 0.04) continue;
    ctx.strokeStyle = `rgba(255,255,255,${(0.85 * f).toFixed(3)})`; ctx.lineWidth = DPR * (0.6 + 1.2 * f);
    ctx.beginPath(); for (const s of b.strengen) { ctx.moveTo(s[0] + Math.cos(s[3]) * s[2], s[1] + Math.sin(s[3]) * s[2]); ctx.arc(s[0], s[1], s[2], s[3], s[4], s[5]); } ctx.stroke();
  }
  // de cellen: een dunne rand, de groepen als stipjes, de uitvoer als dichte ring; de aangewezen cel feller
  const klein = `500 ${Math.max(8.5 * DPR, fs * 0.72)}px "JetBrains Mono", ui-monospace, monospace`;
  for (const p of proj) {
    const st = vorm[p.k], licht = hover.station === p.k;
    if (st.soort === "laag") {
      ctx.strokeStyle = licht ? "rgba(255,255,255,0.9)" : "rgba(255,255,255,0.28)"; ctx.lineWidth = DPR * (licht ? 1.6 : 0.9);
      ctx.beginPath(); ctx.arc(p.cx, p.cy, p.r, 0, 7); ctx.stroke();
      ctx.fillStyle = "rgba(255,255,255,0.35)";
      for (let i = 0; i < st.n; i++) { const a = glad[p.k][i]; ctx.fillStyle = `rgba(255,255,255,${(0.25 + 0.6 * a).toFixed(2)})`; ctx.beginPath(); ctx.arc(p.pt[2 * i], p.pt[2 * i + 1], DPR * (1.1 + 0.9 * a), 0, 7); ctx.fill(); }
    } else if (st.soort === "in") {
      for (let i = 0; i < st.n; i++) { const a = glad[p.k][i]; ctx.fillStyle = `rgba(255,255,255,${(0.3 + 0.6 * a).toFixed(2)})`; ctx.beginPath(); ctx.arc(p.pt[2 * i], p.pt[2 * i + 1], DPR * (1.3 + 0.9 * a), 0, 7); ctx.fill(); }
      ctx.strokeStyle = licht ? "rgba(255,255,255,0.7)" : "rgba(255,255,255,0.10)"; ctx.lineWidth = DPR; ctx.setLineDash([3 * DPR, 5 * DPR]);
      ctx.beginPath(); ctx.ellipse(p.cx, p.cy, p.r * 1.1, p.r * 0.9, 0, 0, 7); ctx.stroke(); ctx.setLineDash([]);
    } else {
      const a = glad[p.k][0];
      ctx.strokeStyle = `rgba(255,255,255,${(0.5 + 0.5 * a).toFixed(2)})`; ctx.lineWidth = DPR * (2.5 + 2 * a);
      ctx.beginPath(); ctx.arc(p.cx, p.cy, p.r, 0, 7); ctx.stroke();
    }
    // het label: cyaan kaartje met de naam, ernaast in grijs wat de kijker erin ziet
    const [naam, soort] = NAMEN[p.k] || ["", ""];
    const ln = (stand && Array.isArray(stand.laagnamen)) ? stand.laagnamen.find(x => x && x.laag === p.k) : null;
    const lx = p.cx + p.r * 0.72 + fs * 0.4, ly = p.cy - p.r * 0.72 - fs * 1.1;
    ctx.font = klein; ctx.textBaseline = "middle"; ctx.textAlign = "left";
    const bw = ctx.measureText(naam.toUpperCase()).width + fs * 0.8, bh = fs * 1.1;
    ctx.fillStyle = licht ? "rgba(255,255,255,0.95)" : `rgba(${CYAAN},0.85)`; ctx.fillRect(lx, ly - bh / 2, bw, bh);
    ctx.fillStyle = "#06090C"; ctx.fillText(naam.toUpperCase(), lx + fs * 0.45, ly + DPR * 0.5);
    ctx.fillStyle = "rgba(255,255,255,0.55)";
    ctx.fillText(st.soort === "laag" ? `${soort}${ln && ln.sterkte ? " · " + (+ln.sterkte).toFixed(2).replace(".", ",") + "×" : ""}` : (st.soort === "in" ? `${st.n} groepen` : "het antwoord"), lx + bw + fs * 0.5, ly);
  }
  ctx.textBaseline = "alphabetic"; ctx.globalAlpha = 1;
}

/* ---- de laag open: kanalen, matrices, bouw (de microscoop) ---- */
function tekenLaag(t, j, alpha) {
  const k = zoom.laag; if (k === null) return;
  const fs = P.fs, mono = `500 ${fs}px "JetBrains Mono", ui-monospace, Consolas, monospace`;
  const Hv = H - P.boven, mu = muis ? {x: muis.x, y: muis.y - P.boven} : null;
  ctx.save(); ctx.translate(0, P.boven);
  ctx.globalAlpha = alpha;
  ctx.fillStyle = "rgba(7,10,20,0.94)"; ctx.fillRect(0, 0, B, Hv);
  const [naam, soort] = NAMEN[k] || ["", ""];
  ctx.font = mono; ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
  ctx.fillStyle = "rgba(142,153,179,0.95)"; ctx.fillText("← terug (Esc)", fs * 1.2, fs * 2);
  ctx.font = `700 ${fs * 1.5}px "JetBrains Mono", ui-monospace, monospace`; ctx.fillStyle = "rgba(234,238,247,0.95)";
  ctx.fillText(naam, fs * 12, fs * 2.1);
  ctx.font = mono; ctx.fillStyle = kleurVan(soort); ctx.fillText(soort, fs * 12 + naam.length * fs * 0.95 + fs, fs * 2.05);
  ctx.fillStyle = "rgba(92,103,129,0.9)"; ctx.textAlign = "right"; ctx.fillText("← → andere laag", B - fs * 1.2, fs * 2); ctx.textAlign = "left";

  const top = fs * 3.6, hoog = Hv - top - fs * 3.2;
  const rij = (j >= 0 && rijen[j]) ? rijen[j] : null, v = rij ? (rij[k] || []) : [], m = kolMax[k];
  const kan = fijnKanaal(j, k), ffe = fijnFfEenheid(k), kopv = fijnKop(j, k);
  const rasterB = Math.min(B * 0.34, hoog * 0.95), cel = Math.min(rasterB / 24, hoog * 0.5 / 16), rasterH = cel * 16;
  const rx = fs * 1.2, ry = top + fs * 1.2;
  ctx.fillStyle = "rgba(92,103,129,0.9)"; ctx.fillText(KOL[k] === 1 ? "1 knoop — haar zekerheid" : kan ? `${spec.breedte} kanalen · licht is activiteit nu` : `${spec.breedte} kanalen · in 32 groepen · licht is nu`, rx, ry - fs * 0.6);
  let aanw = null;
  if (KOL[k] === 1) {
    const a = v.length ? Math.min(1, (v[0] || 0) / m) : 0;
    ctx.fillStyle = `rgba(200,240,225,${(0.3 + 0.7 * a).toFixed(2)})`; ctx.beginPath(); ctx.arc(rx + rasterB / 2, ry + rasterH / 2, rasterH * 0.18 * (0.8 + 0.4 * a), 0, 7); ctx.fill();
  } else {
    for (let c = 0; c < 384; c++) {
      const g = Math.floor(c / 12), a = kan ? (kan[c] || 0) / 255 : (v.length ? Math.min(1, (v[g] || 0) / m) : 0);
      const x = rx + (c % 24) * cel, y = ry + Math.floor(c / 24) * cel;
      ctx.fillStyle = `rgba(${127 + 100 * a | 0},${224 + 20 * a | 0},${195 + 50 * a | 0},${(0.12 + 0.85 * a * a).toFixed(3)})`;
      ctx.fillRect(x + 1, y + 1, cel - 2, cel - 2);
      if (mu && mu.x >= x && mu.x < x + cel && mu.y >= y && mu.y < y + cel) aanw = `kanaal ${c}${kan ? "" : ` (groep ${g})`} · activiteit ${(a * 100).toFixed(0)}% van het max van deze laag`;
    }
    if (ffe && ffe.length) {
      const fcel = Math.min(rasterB / 48, (hoog - rasterH - fs * 3.6) / 32), fy0 = ry + rasterH + fs * 2.2;
      ctx.fillStyle = "rgba(92,103,129,0.9)"; ctx.fillText(`${ffe.length} feedforward-eenheden · gemiddeld in deze gedachte`, rx, fy0 - fs * 0.6);
      for (let u = 0; u < ffe.length; u++) {
        const a = (ffe[u] || 0) / 255, x = rx + (u % 48) * fcel, y = fy0 + Math.floor(u / 48) * fcel;
        ctx.fillStyle = `rgba(${127 + 100 * a | 0},${224 + 20 * a | 0},${195 + 50 * a | 0},${(0.1 + 0.9 * a * a).toFixed(3)})`;
        ctx.fillRect(x + 0.5, y + 0.5, Math.max(0.5, fcel - 1), Math.max(0.5, fcel - 1));
        if (mu && mu.x >= x && mu.x < x + fcel && mu.y >= y && mu.y < y + fcel) aanw = `feedforward-eenheid ${u} · gemiddeld ${(a * 100).toFixed(0)}% van het max in deze laag`;
      }
    }
  }
  const mx = rx + rasterB + fs * 2.5, mB = Math.min(B - mx - fs * 12.5, hoog * 0.9), mcel = mB / 32, my = top + (hoog - mB) / 2;
  const M = (k < KOL.length - 2 && bedrading) ? bedrading[k] : null;
  ctx.fillStyle = "rgba(92,103,129,0.9)";
  if (M) {
    ctx.fillText(`bedrading naar ${NAMEN[k + 1][0]} · 32 × 32 groepen · mint plus, koraal min`, mx, my - fs * 0.8);
    for (let d = 0; d < 32; d++) for (let b = 0; b < 32; b++) {
      const w = M[d] ? (M[d][b] || 0) : 0, x = mx + b * mcel, y = my + d * mcel;
      ctx.fillStyle = warm(w); ctx.fillRect(x + 0.5, y + 0.5, mcel - 1, mcel - 1);
      if (mu && mu.x >= x && mu.x < x + mcel && mu.y >= y && mu.y < y + mcel) aanw = `van groep ${b} (${NAMEN[k][0]}) naar groep ${d} (${NAMEN[k + 1][0]}): ${w >= 0 ? "+" : ""}${w.toFixed(3)}`;
    }
    ctx.fillStyle = "rgba(92,103,129,0.8)"; ctx.textAlign = "left";
    ctx.fillText("bron →", mx, my + mB + fs * 1.2); ctx.save(); ctx.translate(mx - fs * 0.6, my + mB); ctx.rotate(-Math.PI / 2); ctx.fillText("doel →", 0, 0); ctx.restore();
  } else if (k === KOL.length - 2 && bedradingUit) {
    ctx.fillText("bedrading naar de uitvoer · per groep", mx, my - fs * 0.8);
    const bw = mB / 32;
    for (let b = 0; b < 32; b++) { const w = bedradingUit[b] || 0, h = Math.abs(w) * mB * 0.9; ctx.fillStyle = warm(w); ctx.fillRect(mx + b * bw + 1, my + mB - h, bw - 2, h);
      if (mu && mu.x >= mx + b * bw && mu.x < mx + (b + 1) * bw && mu.y >= my && mu.y < my + mB) aanw = `groep ${b} → uitvoer: ${w >= 0 ? "+" : ""}${w.toFixed(3)}`; }
  } else {
    ctx.fillText(k === KOL.length - 1 ? "de uitvoer: hier wordt haar antwoord een teken" : "de inbedding: tekens worden 384 getallen", mx, my - fs * 0.8);
  }
  const bx = B - fs * 10.5, by = top + fs * 0.4;
  ctx.fillStyle = "rgba(92,103,129,0.9)"; ctx.fillText("de bouw", bx, by);
  const regels = KOL[k] === 1 ? [["uitvoer", "1 knoop"], ["zekerheid", "softmax"]] : k === 0 ? [["inbedding", `${spec.breedte}`], ["positie", "rotatie"]] :
    [["aandacht", `${spec.koppen} koppen × 64`], ["feedforward", `${spec.verborgen} eenheden`], ["stroom", `${spec.breedte} kanalen`], ["normalisatie", "2×"]];
  ctx.font = mono;
  regels.forEach(([a, b], i) => { const y = by + fs * 2.3 * (i + 1); ctx.fillStyle = "rgba(234,238,247,0.85)"; ctx.fillText(a, bx, y); ctx.fillStyle = "rgba(142,153,179,0.95)"; ctx.fillText(b, bx, y + fs * 1.05); });
  if (kopv) {
    const ky = by + fs * 2.3 * (regels.length + 1) + fs * 2.6, kw = fs * 8;
    ctx.fillStyle = "rgba(92,103,129,0.9)"; ctx.fillText(`${kopv.length} koppen · nu`, bx, ky - fs * 0.6);
    kopv.forEach((val, h) => {
      const a = (val || 0) / 255, y = ky + h * fs * 1.15;
      ctx.fillStyle = "rgba(21,28,48,1)"; ctx.fillRect(bx, y, kw, fs * 0.75);
      ctx.fillStyle = `rgba(${240 - 60 * a | 0},${168 + 60 * a | 0},${255 - 30 * a | 0},0.9)`; ctx.fillRect(bx, y, kw * a, fs * 0.75);
      if (mu && mu.x >= bx && mu.x < bx + kw && mu.y >= y && mu.y < y + fs * 0.75) aanw = `kop ${h + 1} · activiteit nu ${(a * 100).toFixed(0)}% van het max van deze laag`;
    });
  }
  const ln = (stand && Array.isArray(stand.laagnamen)) ? stand.laagnamen.find(x => x && x.laag === k) : null;
  if (ln && ln.sterkte) { const ny = by + fs * 2.3 * (regels.length + 1) + (kopv ? fs * 2.6 + kopv.length * fs * 1.15 + fs * 1.2 : 0); ctx.fillStyle = "rgba(92,103,129,0.9)"; ctx.fillText(`naam uit de meting:`, bx, ny); ctx.fillStyle = kleurVan(ln.naam); ctx.fillText(`${ln.naam} (${(+ln.sterkte).toFixed(2)}×)`, bx, ny + fs * 1.05); }
  ctx.fillStyle = aanw ? "rgba(234,238,247,0.95)" : "rgba(92,103,129,0.8)"; ctx.textAlign = "left";
  ctx.fillText(aanw || "wijs een kanaal of een vakje aan", fs * 1.2, Hv - fs * 1.2);
  ctx.globalAlpha = 1; ctx.restore();
}

/* ---- elk beeld ---- */
let laatstMeld = 0, beelden = 0;
const FOTO = /foto=1/.test(location.search);        // proefopname: na 40 beelden stoppen
// de kijker bewaart de laatste 48 doorgangen; bij een langer antwoord begint
// de eerste dus niet bij het lezen van de vraag maar bij een teken verderop
const verschuiving = () => Math.max(0, antwoordDoel.length + 1 - rijen.length);
function teken(t) {
  ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
  ctx.clearRect(0, 0, B, H);
  if (!rijen.length && wachtrij.length) nieuweGedachte(t);
  const n = rijen.length;
  let j = -1, veeg = 0;
  if (n) {
    if (LIVE && vast === null) { j = n - 1; veeg = 1; }
    else if (vast !== null) { j = Math.min(n - 1, vast); veeg = 1; }
    else {
      const u = (t - speelStart) / 1000 / TEKEN_S;
      j = Math.min(n - 1, Math.floor(u)); veeg = Math.min(1, (u - Math.floor(u)) / VEEG);
      if (j >= n - 1 && !klaarSinds && (u - (n - 1)) > 1) klaarSinds = t;
      if (j >= n - 1 && klaarSinds) veeg = 1;
    }
    antwoordNu = Math.max(0, Math.min(antwoordDoel.length, j + verschuiving()));
    if (t - laatstTonen > 80) { laatstTonen = t; const a = document.getElementById("antwoord"); if (a) a.textContent = antwoordDoel.slice(0, antwoordNu); if (typeof toonGedachte === "function") toonGedachte(j, n); }
  }
  // de ruimte draait zachtjes als je even niets doet
  if (vuil) projecteer();
  zoekHover();
  zoom.t += ((zoom.doel || 0) - zoom.t) * 0.12;
  if (Math.abs(zoom.t - (zoom.doel || 0)) < 0.002) zoom.t = zoom.doel || 0;
  if (zoom.t < 0.999) tekenRuimte(t, j, veeg, 1 - zoom.t);
  if (zoom.t > 0.001 && zoom.laag !== null) tekenLaag(t, j, zoom.t);
  doek.style.cursor = sleep ? "grabbing" : (hover.station !== null || zoom.t > 0.5) ? "pointer" : "default";
  if (t - laatstMeld > 100) { laatstMeld = t; if (typeof toonOnderschrift === "function") toonOnderschrift(j, n); }
  if (!LIVE && n && vast === null && klaarSinds && t - klaarSinds > 7000) { if (wachtrij.length) nieuweGedachte(t); else { speelStart = t; klaarSinds = 0; } }
  if (!FOTO || ++beelden < 40) requestAnimationFrame(teken);
}
requestAnimationFrame(teken);
