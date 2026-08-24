/* ======================================================================
   De Sterrenwacht — Claudes ontwerp, van de grond af (24 aug 2026, Cley:
   "begin vanaf nul tot je eigen futuristische design").

   Geen website met bladen. Eén scherm. Haar brein in het midden, in de
   ruimte: 22 stations achter elkaar (de inbedding, 20 lagen, de uitvoer).
   Elke laag is een schijf van 384 punten -- elk punt een echt kanaal van
   haar residustroom, op een spiraal zodat ze de schijf gelijk vullen.
   Om elke schijf: 6 aandachtskoppen (de ruiten) en de feedforward in 48
   groepen (de streepjes). Tussen de stations haar echte bedrading: de
   sterkste gewichten van groep naar groep, mint plus, koraal min.
   Het licht dat erdoorheen trekt is haar gemeten activiteit, per
   geschreven teken, per kanaal. Draaien met de muis, klik op een laag en
   de microscoop gaat open. Niets flitst; de ruimte draait langzaam als je
   even niets doet.
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

/* ---- de vorm: waar elk punt in de ruimte zit ---- */
const GOUD = Math.PI * (3 - Math.sqrt(5));
let vorm = [];                           // per station: {z, xy: Float32Array, groep: [[x,y]], kop: [[x,y]], ff: [[x1,y1,x2,y2]], n}
function bouwVorm() {
  const n = KOL.length, dz = 1.1;
  vorm = [];
  for (let k = 0; k < n; k++) {
    const z = (k - (n - 1) / 2) * dz;
    const st = {z, k, groep: [], kop: [], ff: [], n: 0, xy: null, soort: "laag"};
    if (KOL[k] === 1) { st.soort = "uit"; st.xy = new Float32Array([0, 0]); st.n = 1; st.groep = [[0, 0]]; }
    else if (k === 0) {                  // de inbedding: de 32 groepen als ring
      st.soort = "in"; st.n = KOL[k]; st.xy = new Float32Array(st.n * 2);
      for (let g = 0; g < st.n; g++) { const a = -Math.PI / 2 + g / st.n * 2 * Math.PI; st.xy[2 * g] = Math.cos(a) * 0.85; st.xy[2 * g + 1] = Math.sin(a) * 0.85; st.groep.push([st.xy[2 * g], st.xy[2 * g + 1]]); }
    } else {                             // een laag: 384 kanalen in 32 taartpunten van 12 (de groepen van de kijker)
      const N = spec.breedte, per = Math.max(1, Math.floor(N / KOL[k])), G = KOL[k];
      st.n = N; st.xy = new Float32Array(N * 2);
      const som = [];
      for (let c = 0; c < N; c++) {
        const g = Math.min(G - 1, Math.floor(c / per)), i = c - g * per;
        const rijen4 = Math.max(1, Math.round(per / 3)), q = Math.floor(i / 3), o = (i % 3) - 1;
        const r = 0.28 + 0.72 * (q + 0.5) / rijen4, a = -Math.PI / 2 + (g + 0.5 + o * 0.3) / G * 2 * Math.PI;
        st.xy[2 * c] = Math.cos(a) * r; st.xy[2 * c + 1] = Math.sin(a) * r;
        (som[g] = som[g] || [0, 0, 0]); som[g][0] += st.xy[2 * c]; som[g][1] += st.xy[2 * c + 1]; som[g][2] += 1;
      }
      for (let g = 0; g < KOL[k]; g++) { const s = som[g] || [0, 0, 1]; st.groep.push([s[0] / s[2], s[1] / s[2]]); }
      for (let h = 0; h < spec.koppen; h++) { const a = -Math.PI / 2 + h / spec.koppen * 2 * Math.PI; st.kop.push([Math.cos(a) * 1.22, Math.sin(a) * 1.22]); }
      for (let i = 0; i < 48; i++) { const a = -Math.PI / 2 + (i + 0.5) / 48 * 2 * Math.PI; st.ff.push([Math.cos(a) * 1.36, Math.sin(a) * 1.36, Math.cos(a) * 1.48, Math.sin(a) * 1.48]); }
    }
    vorm.push(st);
  }
  // de lijnen: per overgang de sterkste gewichten van groep naar groep
  lijnen = [];
  for (let k = 0; k < n - 1; k++) {
    let wmax = 0.0001;
    const M = (k < n - 2 && bedrading) ? bedrading[k] : null, U = (k === n - 2) ? bedradingUit : null;
    const alle = [];
    if (M) for (let d = 0; d < M.length; d++) for (let b = 0; b < (M[d] || []).length; b++) alle.push([Math.abs(M[d][b]), M[d][b], b, d]);
    else if (U) for (let b = 0; b < U.length; b++) alle.push([Math.abs(U[b]), U[b], b, 0]);
    alle.sort((p, q) => q[0] - p[0]);
    const top = alle.slice(0, U ? 32 : 36);
    for (const [, w] of top) wmax = Math.max(wmax, Math.abs(w));
    for (const [, w, b, d] of top) lijnen.push({k, w, b, d, a: Math.abs(w) / wmax});
  }
  vuil = true;
}
let lijnen = [];
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
  if (typeof bouwGedachte === "function") bouwGedachte();
}

/* ---- de camera ---- */
const cam = {yaw: 0.5, pitch: 0.28, D: 24, f: 18, zoom: 1};
let vuil = true, S = 100, CX = 0, CY = 0, laatstBediend = 0;
let proj = [];                           // per station: {xy: Float32Array (schermpunten), s: schaal, z: diepte, cx, cy, r, groep, kop, ff}
function projecteer() {
  const cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw), cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
  // eerst op schaal 1 om het midden: dan past de tekening in het vrije vak,
  // wat de hoek ook is (de verre kant klein, de nabije groot)
  const ruw = (x, y, z) => {
    const x1 = x * cy + z * sy, z1 = -x * sy + z * cy;
    const y2 = y * cp - z1 * sp, z2 = y * sp + z1 * cp;
    const s = cam.f / (cam.D + z2);
    return [x1 * s, -y2 * s, z2, s];
  };
  let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
  for (const st of vorm) { const c = ruw(0, 0, st.z), r = 1.5 * c[3]; x0 = Math.min(x0, c[0] - r); x1 = Math.max(x1, c[0] + r); y0 = Math.min(y0, c[1] - r); y1 = Math.max(y1, c[1] + r); }
  S = Math.min(P.vrijB / (x1 - x0), P.vrijH / (y1 - y0)) * 0.94 * cam.zoom;
  CX = P.vrijX + P.vrijB / 2 - (x0 + x1) / 2 * S; CY = P.vrijY + P.vrijH / 2 - (y0 + y1) / 2 * S;
  const pt = (x, y, z) => { const q = ruw(x, y, z); return [CX + q[0] * S, CY + q[1] * S, q[2], q[3]]; };
  proj = vorm.map(st => {
    const [cx, cyy, z2, s] = pt(0, 0, st.z);
    const xy = new Float32Array(st.n * 2);
    for (let i = 0; i < st.n; i++) { const p = pt(st.xy[2 * i], st.xy[2 * i + 1], st.z); xy[2 * i] = p[0]; xy[2 * i + 1] = p[1]; }
    return {k: st.k, xy, s, z: z2, cx, cy: cyy, r: s * S,
            groep: st.groep.map(g => pt(g[0], g[1], st.z)), kop: st.kop.map(g => pt(g[0], g[1], st.z)),
            ff: st.ff.map(f => [pt(f[0], f[1], st.z), pt(f[2], f[3], st.z)])};
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
    if (sleep.bewogen && zoom.t < 0.5) { cam.yaw = sleep.yaw + dx * 0.006; cam.pitch = Math.max(-1.3, Math.min(1.3, sleep.pitch + dy * 0.006)); vuil = true; }
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
  // eerst een punt (een kanaal), dan een station (een laag)
  let bd = (7 * DPR) ** 2, best = null;
  for (const p of proj) for (let i = 0; i < p.xy.length; i += 2) {
    const d = (p.xy[i] - muis.x) ** 2 + (p.xy[i + 1] - muis.y) ** 2;
    if (d < bd) { bd = d; best = [p.k, i / 2]; }
  }
  if (best) { hover.station = best[0]; hover.kanaal = best[1]; return; }
  let sd = 1e18, sk = null;
  for (const p of proj) { const d = Math.hypot(p.cx - muis.x, p.cy - muis.y); if (d < p.r * 1.55 && d < sd) { sd = d; sk = p.k; } }
  hover.station = sk;
}

/* ---- helpers ---- */
function rondRect(q, x, y, w, h, r) { q.beginPath(); q.moveTo(x + r, y); q.arcTo(x + w, y, x + w, y + h, r); q.arcTo(x + w, y + h, x, y + h, r); q.arcTo(x, y + h, x, y, r); q.arcTo(x, y, x + w, y, r); q.closePath(); }
function warm(v) {                       // gewicht -> kleur
  const a = Math.min(1, Math.abs(v));
  return v >= 0 ? `rgba(127,224,195,${(0.08 + 0.92 * a).toFixed(3)})` : `rgba(255,154,122,${(0.08 + 0.92 * a).toFixed(3)})`;
}
const TRAP = 16, KLEUR_TRAP = [];
for (let i = 0; i <= TRAP; i++) {
  const a = i / TRAP, u = Math.min(1, a * 2), w = Math.max(0, a * 2 - 1);      // warm bleek -> mint -> wit
  const r = (1 - u) * 172 + u * 127, g = (1 - u) * 172 + u * 224, b = (1 - u) * 158 + u * 195;
  KLEUR_TRAP.push(`rgba(${r + (240 - r) * w | 0},${g + (255 - g) * w | 0},${b + (235 - b) * w | 0},${(0.42 + 0.58 * a).toFixed(3)})`);
}
const KLEUR_STIL = "rgba(172,172,158,0.18)";

/* ---- de ruimte: elk beeld ---- */
function tekenRuimte(t, j, veeg, alpha) {
  if (vuil || !proj.length) projecteer();
  ctx.globalAlpha = alpha;
  const rij = (j >= 0 && rijen[j]) ? rijen[j] : null, n = KOL.length;
  const front = veeg * (n + 1);
  const volgorde = proj.slice().sort((a, b) => b.z - a.z);            // ver eerst
  const zmin = Math.min(...proj.map(p => p.z)), zmax = Math.max(...proj.map(p => p.z));
  const nabij = p => 1 - (p.z - zmin) / Math.max(0.001, zmax - zmin);   // 1 = dichtbij
  // de bedrading: van station naar station
  ctx.lineCap = "round";
  for (const l of lijnen) {
    const a = proj[l.k], b = proj[l.k + 1]; if (!a || !b) continue;
    const g1 = a.groep[l.b], g2 = b.groep[l.d]; if (!g1 || !g2) continue;
    const nb = (nabij(a) + nabij(b)) / 2;
    ctx.strokeStyle = l.w >= 0 ? `rgba(165,232,205,${(0.06 + 0.34 * l.a * (0.5 + 0.5 * nb)).toFixed(3)})` : `rgba(255,172,150,${(0.06 + 0.34 * l.a * (0.5 + 0.5 * nb)).toFixed(3)})`;
    ctx.lineWidth = DPR * (0.5 + 1.3 * l.a) * a.s;
    ctx.beginPath(); ctx.moveTo(g1[0], g1[1]); ctx.lineTo(g2[0], g2[1]); ctx.stroke();
  }
  // het licht van het teken dat nu door haar heen trekt
  if (rij && front > 0 && front < n + 1) {
    const kf = Math.max(0, Math.min(n - 1, front - 1)), k0 = Math.floor(kf), k1 = Math.min(n - 1, k0 + 1), u = kf - k0;
    const a0 = proj[k0], a1 = proj[k1];
    const lx = a0.cx + (a1.cx - a0.cx) * u, ly = a0.cy + (a1.cy - a0.cy) * u, lr = (a0.r + (a1.r - a0.r) * u) * 1.7;
    const lg = ctx.createRadialGradient(lx, ly, 0, lx, ly, lr);
    lg.addColorStop(0, "rgba(200,235,255,0.13)"); lg.addColorStop(1, "rgba(200,235,255,0)");
    ctx.fillStyle = lg; ctx.fillRect(lx - lr, ly - lr, 2 * lr, 2 * lr);
  }
  // de stations, ver naar dichtbij
  for (const p of volgorde) {
    const k = p.k, st = vorm[k], nb = nabij(p);
    const aan = rij ? Math.max(0, Math.min(1, front - k + 1)) : 0;
    const v = rij ? (rij[k] || []) : [], m = kolMax[k];
    const kan = rij ? fijnKanaal(j, k) : null, kop = rij ? fijnKop(j, k) : null, ffg = rij ? fijnFfGroep(j, k) : null;
    ctx.globalAlpha = alpha * (0.5 + 0.5 * nb);
    // de omtrek van de laag: een zachte ring, feller als je hem aanwijst
    if (st.soort === "laag") {
      const licht = hover.station === k && hover.kanaal === null;
      ctx.strokeStyle = licht ? "rgba(234,238,247,0.6)" : `rgba(120,140,190,${(0.20 + 0.15 * aan).toFixed(2)})`; ctx.lineWidth = DPR * (licht ? 1.4 : 0.8);
      ctx.beginPath();
      st.ff.forEach((f, i) => { const q = p.ff[i][0]; if (i === 0) ctx.moveTo(q[0], q[1]); else ctx.lineTo(q[0], q[1]); }); ctx.closePath(); ctx.stroke();
      // de feedforward: 48 streepjes
      for (let i = 0; i < 48; i++) {
        const a = ffg ? (ffg[i] || 0) / 255 * aan : 0, [q1, q2] = p.ff[i];
        ctx.strokeStyle = ffg ? KLEUR_TRAP[Math.round(a * TRAP)] : KLEUR_STIL; ctx.lineWidth = DPR * (0.8 + 1.2 * a) * p.s;
        ctx.beginPath(); ctx.moveTo(q1[0], q1[1]); ctx.lineTo(q2[0], q2[1]); ctx.stroke();
      }
      // de koppen: ruiten
      for (let h = 0; h < p.kop.length; h++) {
        const a = kop ? (kop[h] || 0) / 255 * aan : 0, [qx, qy] = p.kop[h], r = DPR * (2.2 + 2.4 * a) * p.s;
        ctx.fillStyle = kop ? `rgba(${240 - 60 * a | 0},${168 + 60 * a | 0},${255 - 30 * a | 0},${(0.25 + 0.75 * a).toFixed(2)})` : "rgba(160,180,225,0.3)";
        ctx.beginPath(); ctx.moveTo(qx, qy - r); ctx.lineTo(qx + r, qy); ctx.lineTo(qx, qy + r); ctx.lineTo(qx - r, qy); ctx.closePath(); ctx.fill();
      }
    }
    const per = st.soort === "laag" ? Math.max(1, Math.floor(st.n / Math.max(1, KOL[k]))) : 1;
    if (st.soort === "laag") {
      ctx.strokeStyle = `rgba(190,192,178,${(0.05 + 0.06 * nb).toFixed(3)})`; ctx.lineWidth = DPR * 0.6 * p.s;
      ctx.beginPath();
      for (let g = 0; g < KOL[k]; g++) for (let i = 0; i < per; i++) {
        const c = g * per + i; if (c >= st.n) break;
        if (i === 0) ctx.moveTo(p.xy[2 * c], p.xy[2 * c + 1]); else ctx.lineTo(p.xy[2 * c], p.xy[2 * c + 1]);
      }
      ctx.stroke();
    }
    // de punten: kanalen (of groepen, of de ene knoop), in emmers van gelijke kleur
    const emmers = new Array(TRAP + 1); for (let i = 0; i <= TRAP; i++) emmers[i] = [];
    const fel = [];                                                    // de felste kanalen krijgen een stille gloed
    for (let i = 0; i < st.n; i++) {
      let a;
      if (!rij) a = 0;
      else if (kan) a = (kan[i] || 0) / 255 * aan;
      else { const g = st.soort === "laag" ? Math.min(KOL[k] - 1, Math.floor(i / per)) : i; a = v.length ? Math.min(1, (v[g] || 0) / m) * aan : 0; }
      // weergave: wortel-achtig, zodat ook half-actieve kanalen te zien zijn (monotoon, dus eerlijk)
      emmers[Math.round(Math.pow(Math.max(0, Math.min(1, a)), 0.7) * TRAP)].push(i);
      if (a > 0.82) fel.push([i, a]);
    }
    const basis = DPR * (st.soort === "laag" ? 1.7 : st.soort === "in" ? 2.6 : 5) * (0.55 + 0.75 * p.s);
    for (let e = 0; e <= TRAP; e++) {
      if (!emmers[e].length) continue;
      const a = e / TRAP, w = basis * (1 + 0.9 * a);
      ctx.fillStyle = rij ? KLEUR_TRAP[e] : "rgba(160,180,225,0.28)";
      ctx.beginPath();
      for (const i of emmers[e]) ctx.rect(p.xy[2 * i] - w / 2, p.xy[2 * i + 1] - w / 2, w, w);
      ctx.fill();
    }
    // de gloed: een stille lichtkring om de felste kanalen van dit teken (geen flits: hij komt op met het licht)
    fel.sort((x, y) => y[1] - x[1]);
    for (const [i, a] of fel.slice(0, 5)) {
      const gx = p.xy[2 * i], gy = p.xy[2 * i + 1], gr = basis * (5 + 6 * a);
      const gg = ctx.createRadialGradient(gx, gy, 0, gx, gy, gr);
      gg.addColorStop(0, `rgba(190,255,215,${(0.30 * a).toFixed(3)})`); gg.addColorStop(1, "rgba(190,255,215,0)");
      ctx.fillStyle = gg; ctx.fillRect(gx - gr, gy - gr, 2 * gr, 2 * gr);
    }
    // het aangewezen kanaal
    if (hover.station === k && hover.kanaal !== null) {
      const i = hover.kanaal; ctx.strokeStyle = "rgba(234,238,247,0.9)"; ctx.lineWidth = DPR;
      ctx.beginPath(); ctx.arc(p.xy[2 * i], p.xy[2 * i + 1], DPR * 5, 0, 7); ctx.stroke();
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
  if (!RUSTIG && zoom.t < 0.5 && !sleep && t - laatstBediend > 15000) { cam.yaw += 0.00022; vuil = true; }
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
