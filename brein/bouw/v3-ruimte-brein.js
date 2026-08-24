/* ======================================================================
   De Sterrenwacht — Claudes ontwerp, van de grond af (24 aug 2026, Cley:
   "begin vanaf nul tot je eigen futuristische design").

   Geen website met bladen. Eén scherm. Haar brein in het midden, als een
   brein (Cley, 24 aug laat: "een echt brein zoals bij een mens"): een
   zijaanzicht vol knopen met een web van dunne lijnen; de vraag komt
   binnen bij de hersenstam, het antwoord komt eruit aan de voorkant. Elke knoop is echt: een groep van 12 kanalen
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

/* ---- de vorm: waar elke knoop in de ruimte zit ---- */
function rnd(seed) {                      // vaste toevalsgetallen: dezelfde knoop staat altijd op dezelfde plek
  let t = (seed | 0) + 0x6D2B79F5; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61);
  return ((t ^ t >>> 14) >>> 0) / 4294967296;
}
let vorm = [], glad = [];                // per station: {k, z, cy, xyz: Float32Array, n, soort}; glad: de getoonde activiteit per knoop
let lijnen = [], samen = [];             // de bedrading tussen de lagen; wie samen vuurt binnen een laag
/* Het brein (Cley, 24 aug: "een echt brein zoals bij een mens, en alleen het draadje licht op").
   Zijaanzicht, de voorkant rechts. De vraag komt binnen bij de hersenstam en de kleine hersenen
   (de inbedding: 32 knopen), gaat in 20 plakken van achter naar voren door de grote hersenen
   (per plak 32 knopen = haar 32 groepen van 12 kanalen; de plakken zijn even vol), en het
   antwoord komt eruit bij de voorkant (de uitvoer: één knoop). De omtrek is tekening; de knopen
   en alle lijnen zijn echt. */
const BREIN = [[-0.95, -0.05], [-1.0, 0.15], [-0.95, 0.35], [-0.8, 0.52], [-0.55, 0.64], [-0.25, 0.70], [0.05, 0.70], [0.35, 0.66],
               [0.6, 0.56], [0.8, 0.42], [0.95, 0.25], [1.0, 0.05], [0.97, -0.12], [0.85, -0.25], [0.65, -0.32], [0.45, -0.30],
               [0.3, -0.36], [0.1, -0.45], [-0.15, -0.48], [-0.4, -0.42], [-0.55, -0.30], [-0.7, -0.22], [-0.85, -0.15]];
const KLEINE = {cx: -0.60, cy: -0.42, rx: 0.27, ry: 0.15};
const STAM = [[-0.30, -0.44], [-0.20, -0.74]];
const UIT = [0.93, -0.20];
function binnen(poly, x, y) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) c = !c;
  }
  return c;
}
function bouwVorm() {
  const n = KOL.length, lagen = n - 2;
  // de plakken: even vol, dus grenzen op kwantielen van de oppervlakte
  const xs = [];
  for (let i = 0; xs.length < 3000 && i < 20000; i++) { const x = rnd(i * 7 + 1) * 2 - 1, y = rnd(i * 7 + 2) * 1.5 - 0.8; if (binnen(BREIN, x, y)) xs.push(x); }
  xs.sort((p, q) => p - q);
  const grens = [-1.0]; for (let k = 1; k < lagen; k++) grens.push(xs[Math.floor(xs.length * k / lagen)]); grens.push(1.0);
  vorm = [];
  for (let k = 0; k < n; k++) {
    const st = {k, z: 0, cy: 0, n: KOL[k], soort: KOL[k] === 1 ? "uit" : (k === 0 ? "in" : "laag"), xyz: new Float32Array(KOL[k] * 3)};
    let sy = 0;
    for (let i = 0; i < st.n; i++) {
      let x, y, pog = 0;
      if (st.soort === "uit") { x = UIT[0]; y = UIT[1]; }
      else if (st.soort === "in") {
        if (i < st.n - 8) { const r = Math.sqrt(rnd(k * 131 + i * 17 + 1)), a = rnd(k * 131 + i * 17 + 2) * 2 * Math.PI; x = KLEINE.cx + Math.cos(a) * r * KLEINE.rx; y = KLEINE.cy + Math.sin(a) * r * KLEINE.ry; }
        else { const u = (i - (st.n - 8) + 0.5) / 8; x = STAM[0][0] + (STAM[1][0] - STAM[0][0]) * u + (rnd(k * 131 + i * 17 + 1) - 0.5) * 0.08; y = STAM[0][1] + (STAM[1][1] - STAM[0][1]) * u; }
      } else {
        const x0 = grens[k - 1], x1 = grens[k];
        do { x = x0 + (x1 - x0) * rnd(k * 131 + i * 17 + pog * 3 + 1); y = rnd(k * 131 + i * 17 + pog * 3 + 2) * 1.5 - 0.8; pog++; }
        while (!binnen(BREIN, x, y) && pog < 400);
      }
      st.xyz[3 * i] = x; st.xyz[3 * i + 1] = y; st.xyz[3 * i + 2] = (rnd(k * 131 + i * 17 + 3) - 0.5) * 0.45; sy += y;
    }
    st.cy = sy / Math.max(1, st.n);
    vorm.push(st);
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
  // per groep de twee sterkste partners -- dat is het web ín een laag
  samen = [];
  if (rijen.length < 4) return;
  for (let k = 0; k < KOL.length; k++) {
    const G = KOL[k]; if (G < 3) continue;
    const reeks = [];
    for (let g = 0; g < G; g++) {
      const v = rijen.map(r => (r[k] || [])[g] || 0), m = v.reduce((p, q) => p + q, 0) / v.length;
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

/* ---- de camera ---- */
const cam = {yaw: 0, pitch: 0, roll: 0, D: 30, f: 22, zoom: 1};
let vuil = true, S = 100, CX = 0, CY = 0, laatstBediend = 0;
let proj = [];                           // per station: {k, xy: Float32Array, s: Float32Array, z, cx, cy}
function projecteer() {
  const cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw), cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch), cr = Math.cos(cam.roll), sr = Math.sin(cam.roll);
  const ruw = (x, y, z) => {
    const x1 = x * cy + z * sy, z1 = -x * sy + z * cy;
    const y2 = y * cp - z1 * sp, z2 = y * sp + z1 * cp;
    const s = cam.f / (cam.D + z2), px = x1 * s, py = -y2 * s;
    return [px * cr - py * sr, px * sr + py * cr, z2, s];
  };
  let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
  for (const st of vorm) for (let i = 0; i < st.n; i++) { const c = ruw(st.xyz[3 * i], st.xyz[3 * i + 1], st.xyz[3 * i + 2]); x0 = Math.min(x0, c[0]); x1 = Math.max(x1, c[0]); y0 = Math.min(y0, c[1]); y1 = Math.max(y1, c[1]); }
  S = Math.min(P.vrijB / (x1 - x0 + 0.6), P.vrijH / (y1 - y0 + 0.6)) * 0.96 * cam.zoom;
  CX = P.vrijX + P.vrijB / 2 - (x0 + x1) / 2 * S; CY = P.vrijY + P.vrijH / 2 - (y0 + y1) / 2 * S;
  proj = vorm.map(st => {
    const xy = new Float32Array(st.n * 2), sc = new Float32Array(st.n);
    for (let i = 0; i < st.n; i++) { const q = ruw(st.xyz[3 * i], st.xyz[3 * i + 1], st.xyz[3 * i + 2]); xy[2 * i] = CX + q[0] * S; xy[2 * i + 1] = CY + q[1] * S; sc[i] = q[3]; }
    const c = ruw(0, st.cy, st.z);
    return {k: st.k, xy, sc, z: c[2], cx: CX + c[0] * S, cy: CY + c[1] * S, s: c[3]};
  });
  vuil = false;
}

/* ---- bediening: draaien, aanwijzen, klikken ---- */
let sleep = null, hover = {station: null, kanaal: null};
function schermXY(e) { const r = doek.getBoundingClientRect(); const p = e.touches ? e.touches[0] : e; return {x: (p.clientX - r.left) * DPR, y: (p.clientY - r.top) * DPR}; }
doek.addEventListener("pointerdown", e => { if (e.button !== 0 && e.pointerType === "mouse") return; sleep = {x: e.clientX, y: e.clientY, yaw: cam.yaw, pitch: cam.pitch, bewogen: false}; doek.setPointerCapture(e.pointerId); laatstBediend = performance.now(); });
doek.addEventListener("pointermove", e => {
  muis = schermXY(e);
  if (sleep) {
    const dx = e.clientX - sleep.x, dy = e.clientY - sleep.y;
    if (Math.hypot(dx, dy) > 4) sleep.bewogen = true;
    if (sleep.bewogen && zoom.t < 0.5) { cam.yaw = Math.max(-0.9, Math.min(0.9, sleep.yaw + dx * 0.006)); cam.pitch = Math.max(-0.6, Math.min(0.6, sleep.pitch + dy * 0.006)); vuil = true; }
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
doek.addEventListener("wheel", e => { if (zoom.t > 0.5) return; e.preventDefault(); cam.zoom = Math.max(0.55, Math.min(2.6, cam.zoom * Math.exp(-e.deltaY * 0.0012))); vuil = true; laatstBediend = performance.now(); }, {passive: false});
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
  let bd = (10 * DPR) ** 2, best = null;
  for (const p of proj) for (let i = 0; i < p.xy.length; i += 2) {
    const d = (p.xy[i] - muis.x) ** 2 + (p.xy[i + 1] - muis.y) ** 2;
    if (d < bd) { bd = d; best = [p.k, i / 2]; }
  }
  if (best) { hover.station = best[0]; hover.kanaal = best[1]; }
}

/* ---- helpers ---- */
function rondRect(q, x, y, w, h, r) { q.beginPath(); q.moveTo(x + r, y); q.arcTo(x + w, y, x + w, y + h, r); q.arcTo(x + w, y + h, x, y + h, r); q.arcTo(x, y + h, x, y, r); q.arcTo(x, y, x + w, y, r); q.closePath(); }
function warm(v) {                       // gewicht -> kleur (de microscoop)
  const a = Math.min(1, Math.abs(v));
  return v >= 0 ? `rgba(127,224,195,${(0.08 + 0.92 * a).toFixed(3)})` : `rgba(255,154,122,${(0.08 + 0.92 * a).toFixed(3)})`;
}
function activiteitVan(j, k, i) {         // een groep in doorgang j: 0..1 ten opzichte van het maximum van die laag in deze gedachte
  const rij = rijen[j]; if (!rij) return 0;
  return Math.min(1, ((rij[k] || [])[i] || 0) / kolMax[k]);
}

/* ---- de ruimte: elk beeld ---- */
function tekenRuimte(t, j, veeg, alpha) {
  if (vuil || !proj.length) projecteer();
  ctx.globalAlpha = alpha;
  const rij = (j >= 0 && rijen[j]) ? rijen[j] : null, n = KOL.length;
  const zmin = Math.min(...proj.map(p => p.z)), zmax = Math.max(...proj.map(p => p.z));
  const nabij = p => 1 - (p.z - zmin) / Math.max(0.001, zmax - zmin);   // 1 = dichtbij
  // Geen golf van links naar rechts (Cley, 24 aug: "daar krijg ik een klein beetje error van").
  // Per teken staat het hele beeld stil; elke knoop glijdt elk beeld een stukje naar zijn waarde
  // van nu, dus niets springt en niets veegt. Licht zit in de knopen die actief zijn en in de
  // draadjes waar iets doorheen gaat: van een actieve knoop naar een actieve knoop.
  for (let k = 0; k < n; k++) { const g = glad[k]; if (!g) continue; for (let i = 0; i < g.length; i++) { const doel = rij ? activiteitVan(j, k, i) : 0; g[i] += (doel - g[i]) * 0.09; } }
  const stroom = (k1, i1, k2, i2) => Math.sqrt(Math.max(0, (glad[k1] ? glad[k1][i1] : 0) * (glad[k2] ? glad[k2][i2] : 0)));
  ctx.lineCap = "round";
  // de omtrek van het brein (tekening, geen meting): grote hersenen, kleine hersenen, hersenstam
  {
    const cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw), cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch), cr = Math.cos(cam.roll), sr = Math.sin(cam.roll);
    const pt = (x, y) => { const x1 = x * cy, z1 = -x * sy, y2 = y * cp - z1 * sp, z2 = y * sp + z1 * cp, s = cam.f / (cam.D + z2), px = x1 * s, py = -y2 * s; return [CX + (px * cr - py * sr) * S, CY + (px * sr + py * cr) * S]; };
    ctx.strokeStyle = "rgba(150,175,190,0.13)"; ctx.lineWidth = DPR * 1.2; ctx.lineJoin = "round";
    ctx.beginPath(); BREIN.forEach(([x, y], i) => { const q = pt(x, y); if (i) ctx.lineTo(q[0], q[1]); else ctx.moveTo(q[0], q[1]); }); ctx.closePath(); ctx.stroke();
    ctx.beginPath(); for (let i = 0; i <= 40; i++) { const a = i / 40 * 2 * Math.PI, q = pt(KLEINE.cx + Math.cos(a) * KLEINE.rx, KLEINE.cy + Math.sin(a) * KLEINE.ry); if (i) ctx.lineTo(q[0], q[1]); else ctx.moveTo(q[0], q[1]); } ctx.stroke();
    const s1 = pt(STAM[0][0] - 0.06, STAM[0][1]), s2 = pt(STAM[1][0] - 0.06, STAM[1][1]), s3 = pt(STAM[1][0] + 0.06, STAM[1][1]), s4 = pt(STAM[0][0] + 0.06, STAM[0][1]);
    ctx.beginPath(); ctx.moveTo(s1[0], s1[1]); ctx.lineTo(s2[0], s2[1]); ctx.moveTo(s4[0], s4[1]); ctx.lineTo(s3[0], s3[1]); ctx.stroke();
  }
  // het web binnen een laag: wie samen vuurt in deze gedachte; licht als er aan beide kanten iets is
  for (const l of samen) {
    const p = proj[l.k]; if (!p) continue;
    const nb = nabij(p), f = stroom(l.k, l.a, l.k, l.b) * l.c;
    ctx.strokeStyle = `rgba(${205 + 40 * f | 0},${210 + 40 * f | 0},${195 + 10 * f | 0},${(0.05 + 0.10 * l.c * (0.4 + 0.6 * nb) + 0.70 * f).toFixed(3)})`;
    ctx.lineWidth = DPR * (0.6 + 1.0 * f) * p.s;
    ctx.beginPath(); ctx.moveTo(p.xy[2 * l.a], p.xy[2 * l.a + 1]); ctx.lineTo(p.xy[2 * l.b], p.xy[2 * l.b + 1]); ctx.stroke();
  }
  // de bedrading tussen de lagen: bleek plus, koraal min; licht waar iets doorheen gaat
  for (const l of lijnen) {
    const a = proj[l.k], b = proj[l.k + 1]; if (!a || !b) continue;
    const nb = (nabij(a) + nabij(b)) / 2, f = stroom(l.k, l.b, l.k + 1, l.d) * (0.4 + 0.6 * l.a);
    ctx.strokeStyle = l.w >= 0 ? `rgba(${228 + 20 * f | 0},${228 + 27 * f | 0},${208 - 20 * f | 0},${(0.06 + 0.14 * l.a * (0.4 + 0.6 * nb) + 0.75 * f).toFixed(3)})`
                               : `rgba(255,${176 + 30 * f | 0},${152 + 20 * f | 0},${(0.06 + 0.14 * l.a * (0.4 + 0.6 * nb) + 0.75 * f).toFixed(3)})`;
    ctx.lineWidth = DPR * (0.5 + 0.6 * l.a + 1.3 * f) * a.s;
    ctx.beginPath(); ctx.moveTo(a.xy[2 * l.b], a.xy[2 * l.b + 1]); ctx.lineTo(b.xy[2 * l.d], b.xy[2 * l.d + 1]); ctx.stroke();
  }
  // de knopen, ver naar dichtbij
  const volgorde = proj.slice().sort((a, b) => b.z - a.z);
  for (const p of volgorde) {
    const k = p.k, st = vorm[k], nb = nabij(p);
    for (let i = 0; i < st.n; i++) {
      const a = glad[k] ? glad[k][i] : 0, x = p.xy[2 * i], y = p.xy[2 * i + 1];
      const r = DPR * (st.n === 1 ? 5 : 2.1) * (0.6 + 0.8 * p.sc[i]);
      // de knopen blijven stil (Cley: "echt alleen het draadje"); hooguit een zweem waar een draadje aankomt
      ctx.fillStyle = `rgba(${118 + 40 * a | 0},${142 + 30 * a | 0},${150 + 10 * a | 0},${(0.20 + 0.14 * nb + 0.12 * a).toFixed(3)})`;
      ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
    }
    if (hover.station === k && hover.kanaal !== null) {
      const i = hover.kanaal; ctx.strokeStyle = "rgba(234,238,247,0.9)"; ctx.lineWidth = DPR;
      ctx.beginPath(); ctx.arc(p.xy[2 * i], p.xy[2 * i + 1], DPR * 7, 0, 7); ctx.stroke();
    }
  }
  ctx.globalAlpha = 1;
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
let laatstMeld = 0;
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
    if (vast !== null) { j = Math.min(n - 1, vast); veeg = 1; }
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
  if (!RUSTIG && zoom.t < 0.5 && !sleep && t - laatstBediend > 15000) { cam.yaw += (0.10 * Math.sin(t / 7000) - cam.yaw) * 0.01; cam.pitch += (0.05 * Math.sin(t / 11000) - cam.pitch) * 0.01; vuil = true; }
  if (vuil) projecteer();
  zoekHover();
  zoom.t += ((zoom.doel || 0) - zoom.t) * 0.12;
  if (Math.abs(zoom.t - (zoom.doel || 0)) < 0.002) zoom.t = zoom.doel || 0;
  if (zoom.t < 0.999) tekenRuimte(t, j, veeg, 1 - zoom.t);
  if (zoom.t > 0.001 && zoom.laag !== null) tekenLaag(t, j, zoom.t);
  doek.style.cursor = sleep ? "grabbing" : (hover.station !== null || zoom.t > 0.5) ? "pointer" : "grab";
  if (t - laatstMeld > 100) { laatstMeld = t; if (typeof toonOnderschrift === "function") toonOnderschrift(j, n); }
  if (n && vast === null && klaarSinds && t - klaarSinds > 7000) { if (wachtrij.length) nieuweGedachte(t); else { speelStart = t; klaarSinds = 0; } }
  requestAnimationFrame(teken);
}
requestAnimationFrame(teken);
