/* ======================================================================
   De microscoop — Claudes ontwerp voor het weefsel (24 aug 2026, na drie
   pogingen en Cleys eerlijke "dat ben jij niet").

   Dit is wat ik zelf zou willen als ik naar haar kijk: niet een plaatje,
   maar iets waar je dichterbij kunt kijken. In het overzicht staat haar
   hele bouw als één stroom: per laag de aandacht (6 koppen), de
   feedforward (1536 eenheden) en de residustroom van 384 kanalen die er
   doorheen loopt; tussen de lagen de sterkte van haar bedrading. Het licht
   stroomt per geschreven teken door de stroom -- haar echte gemeten
   activiteit. Klik op een laag en hij gaat open: haar 384 kanalen als
   raster met hun activiteit, en haar gewichtsmatrix naar de volgende laag
   als warmtekaart, 32 x 32, elk vakje een echt getal. Wijs iets aan en het
   getal staat er. Pijltjes van laag naar laag, Esc terug. Alles glijdt,
   niets flitst.

   Echt: de bouw, de kanalen, de matrices, de activiteit, elk getal. Regie:
   het tempo van het licht. Nog niet gemeten (tot de kijker fijner is): de
   activiteit per kop en per feedforward-eenheid -- die staan als bouw,
   eerlijk gelabeld.
   ====================================================================== */
const doek = document.getElementById("doek");
const ctx = doek.getContext("2d");
const DPR = Math.min(devicePixelRatio || 1, 2);
let B = 1, H = 1;
let KOL = [32, 32, 32, 32, 32, 32, 32, 32, 32, 1];
let NAMEN = [];
let stand = null, wachtrij = [], rijNu = null, rijStart = 0;
let gloed = [], kolMax = KOL.map(() => 0.0001);
let bedrading = null, bedradingUit = null, weefsel = [];
let vonken = [];
let antwoordDoel = "", antwoordNu = 0, laatstTonen = 0;
const DUUR = 1500;

let rijen = [];                         // doorgangen van deze gedachte: rijen[j][k] = 32 groepen
let sterkte = [];                       // per overgang: {plus, min, p, m}
let speelStart = 0, klaarSinds = 0, muis = null;
const TEKEN_S = 0.7, VEEG = 0.5;
let laagnamen = {};
let spec = {koppen: 6, verborgen: 1536, breedte: 384};
let zoom = {laag: null, t: 0, van: null};       // t: 0 = overzicht, 1 = open
let fijn = null, fijnTijd = 0, fijnBezig = false;  // de fijne meting: per kanaal, per kop, per eenheid
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
                      tellen: "#C4B5FD", antwoord: "#FDA4AF", antwoordlaag: "#FDA4AF", gesprek: "#F0A8FF"};
const kleurVan = b => FAMILIEKLEUR[b] || (b === "stil" ? "#5C6781" : "#8E99B3");

/* ---- maat ---- */
const P = {fs: 12, links: 0, rechts: 0, boven: 0, onder: 0, stapX: 0, stroomY: 0, stroomH: 0};
function maat() {
  if (!doek.clientWidth) return;
  B = doek.width = Math.round(doek.clientWidth * DPR);
  H = doek.height = Math.round(doek.clientHeight * DPR);
  P.fs = Math.max(10, Math.min(13, B / 115)) * DPR;
  P.links = P.fs * 2.5; P.rechts = P.fs * 2.5; P.boven = P.fs * 3.6; P.onder = P.fs * 4.2;
  P.stapX = (B - P.links - P.rechts) / Math.max(1, KOL.length - 1);
  P.stroomH = Math.max(30, (H - P.boven - P.onder) * 0.36);
  P.stroomY = P.boven + (H - P.boven - P.onder) * 0.5;
}
addEventListener("resize", maat);
if (window.ResizeObserver) new ResizeObserver(() => maat()).observe(document.getElementById("weefsel"));
function laagX(k) { return P.links + k * P.stapX; }

/* ---- bedrading per overgang ---- */
function bouwWeefsel() {
  sterkte = [];
  if (!bedrading) { weefsel = []; return; }
  for (let k = 0; k < KOL.length - 1; k++) {
    let plus = 0, min = 0;
    if (k < KOL.length - 2) {
      const alle = [];
      for (const rij of (bedrading[k] || [])) for (const w of (rij || [])) alle.push(w);
      alle.sort((a, z) => Math.abs(z) - Math.abs(a));
      for (const w of alle.slice(0, 300)) { if (w > 0) plus += w; else min += -w; }
    } else if (bedradingUit) for (const w of bedradingUit) { if (w > 0) plus += w; else min += -w; }
    sterkte.push({plus, min});
  }
  const top = Math.max(0.0001, ...sterkte.map(s => s.plus + s.min));
  for (const s of sterkte) { s.p = s.plus / top; s.m = s.min / top; s.tot = (s.plus + s.min) / top; }
  weefsel = [true];
}
function bouwNamen() {
  NAMEN = [["invoer", "inbedding"]];
  for (let i = 1; i < KOL.length - 1; i++) NAMEN.push(["laag " + i, laagnamen[i] || "GELU"]);
  NAMEN.push(["uitvoer", "zekerheid"]);
  if (stand && stand.run && stand.run.config) {
    const c = stand.run.config;
    spec = {koppen: c.koppen || 6, verborgen: c.verborgen || 1536, breedte: 384};
  }
  maat();
}
bouwNamen();
function nieuweGedachte(t) {
  rijen = wachtrij.slice(); wachtrij = []; rijNu = rijen.length ? rijen[0] : null;
  speelStart = t; klaarSinds = 0; vonken = [];
  kolMax = KOL.map((n, k) => { let m = 0.0001; for (const r of rijen) for (const v of (r[k] || [])) m = Math.max(m, v); return m; });
}

/* ---- bediening: aanwijzen, klikken, pijltjes ---- */
doek.addEventListener("mousemove", e => { const r = doek.getBoundingClientRect(); muis = {x: (e.clientX - r.left) * DPR, y: (e.clientY - r.top) * DPR}; });
doek.addEventListener("mouseleave", () => { muis = null; });
doek.style.cursor = "pointer";
function laagBijMuis() {
  if (!muis) return null;
  let best = null, bd = 1e9;
  for (let k = 0; k < KOL.length; k++) { const d = Math.abs(muis.x - laagX(k)); if (d < bd) { bd = d; best = k; } }
  return bd < P.stapX * 0.6 ? best : null;
}
function openLaag(k) { if (k === null || k < 0 || k >= KOL.length) return; zoom.van = zoom.laag; zoom.laag = k; zoom.doel = 1; }
function sluit() { zoom.doel = 0; }
doek.addEventListener("click", e => {
  if (zoom.t < 0.5) { const k = laagBijMuis(); if (k !== null) openLaag(k); }
  else { const r = doek.getBoundingClientRect(), x = (e.clientX - r.left) * DPR, y = (e.clientY - r.top) * DPR;
         if (y < P.fs * 3.2 && x < P.fs * 9) sluit(); }
});
addEventListener("keydown", e => {
  if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
  if (e.key === "Escape") sluit();
  if (zoom.t > 0.5 && zoom.laag !== null) {
    if (e.key === "ArrowRight") { openLaag(Math.min(KOL.length - 1, zoom.laag + 1)); e.preventDefault(); }
    if (e.key === "ArrowLeft") { openLaag(Math.max(0, zoom.laag - 1)); e.preventDefault(); }
  }
});
zoom.doel = 0;
{ const mm = location.hash.match(/laag=(\d+)/); if (mm) { zoom.laag = +mm[1]; zoom.doel = 1; } }   // #laag=12 opent een laag meteen

/* ---- helpers ---- */
function rondRect(q, x, y, w, h, r) { q.beginPath(); q.moveTo(x + r, y); q.arcTo(x + w, y, x + w, y + h, r); q.arcTo(x + w, y + h, x, y + h, r); q.arcTo(x, y + h, x, y, r); q.arcTo(x, y, x + w, y, r); q.closePath(); }
function warm(v) {                       // gewicht -> kleur
  const a = Math.min(1, Math.abs(v));
  return v >= 0 ? `rgba(127,224,195,${(0.08 + 0.92 * a).toFixed(3)})` : `rgba(255,154,122,${(0.08 + 0.92 * a).toFixed(3)})`;
}

/* ---- het overzicht: de stroom ---- */
function tekenOverzicht(t, j, veeg, alpha) {
  const fs = P.fs, mono = `500 ${fs}px "JetBrains Mono", ui-monospace, Consolas, monospace`;
  ctx.globalAlpha = alpha;
  const front = veeg * (KOL.length + 1);
  const rij = (j >= 0 && rijen[j]) ? rijen[j] : null;
  const n = KOL.length;
  // de stroom tussen de lagen: dikte naar de sterkte van de bedrading, kleur naar plus/min
  for (let k = 0; k < n - 1; k++) {
    const s = sterkte[k] || {tot: 0.4, p: 0.5, m: 0.5}, x1 = laagX(k), x2 = laagX(k + 1);
    const dik = Math.max(3 * DPR, P.stroomH * (0.12 + 0.55 * s.tot));
    const g = ctx.createLinearGradient(x1, 0, x2, 0);
    const mix = s.p / Math.max(0.0001, s.p + s.m);
    g.addColorStop(0, `rgba(${Math.round(255 - 128 * mix)},${Math.round(154 + 70 * mix)},${Math.round(122 + 73 * mix)},0.22)`);
    g.addColorStop(1, `rgba(${Math.round(255 - 128 * mix)},${Math.round(154 + 70 * mix)},${Math.round(122 + 73 * mix)},0.22)`);
    ctx.fillStyle = g;
    ctx.fillRect(x1, P.stroomY - dik / 2, x2 - x1, dik);
    // het licht dat erdoor trekt
    if (rij && front > k && front < k + 2.5) {
      const u = Math.max(0, Math.min(1, front - k - 1));
      const lx = x1 + (x2 - x1) * u;
      const lg = ctx.createRadialGradient(lx, P.stroomY, 0, lx, P.stroomY, P.stapX * 0.9);
      lg.addColorStop(0, "rgba(220,240,255,0.55)"); lg.addColorStop(1, "rgba(220,240,255,0)");
      ctx.fillStyle = lg; ctx.fillRect(x1 - P.stapX, P.stroomY - dik * 2, (x2 - x1) + 2 * P.stapX, dik * 4);
    }
  }
  // per laag: de residustroom als 32 segmenten (de groepen), en de bouw eromheen
  const kolB = Math.max(4 * DPR, Math.min(P.stapX * 0.42, fs * 1.6));
  for (let k = 0; k < n; k++) {
    const x = laagX(k), m = kolMax[k], v = rij ? (rij[k] || []) : [];
    const aan = rij ? Math.max(0, Math.min(1, front - k + 1)) : 0;
    const groepen = KOL[k];
    const segH = P.stroomH / groepen;
    for (let g = 0; g < groepen; g++) {
      const a = v.length ? Math.min(1, (v[g] || 0) / m) * aan : 0;
      const y = P.stroomY - P.stroomH / 2 + g * segH;
      ctx.fillStyle = `rgba(${127 + 100 * a | 0},${224 + 20 * a | 0},${195 + 50 * a | 0},${(0.18 + 0.8 * a * a).toFixed(3)})`;
      ctx.fillRect(x - kolB / 2, y + 0.5, kolB, Math.max(1, segH - 1));
    }
    if (KOL[k] > 1 && k > 0 && k < n - 1) {
      // aandacht (boven) en feedforward (onder): de bouw, met de aantallen
      const bw = Math.min(P.stapX * 0.8, fs * 4.6), bh = fs * 1.6;
      const ay = P.stroomY - P.stroomH / 2 - bh - fs * 0.9, fy = P.stroomY + P.stroomH / 2 + fs * 0.9;
      ctx.fillStyle = `rgba(20,28,50,0.9)`; ctx.strokeStyle = `rgba(120,140,190,${(0.25 + 0.35 * aan).toFixed(2)})`; ctx.lineWidth = 1;
      rondRect(ctx, x - bw / 2, ay, bw, bh, 4 * DPR); ctx.fill(); ctx.stroke();
      rondRect(ctx, x - bw / 2, fy, bw, bh, 4 * DPR); ctx.fill(); ctx.stroke();
      // de 6 koppen als puntjes, de feedforward als fijne streepjes
      const kop = rij ? fijnKop(j, k) : null, ffg = rij ? fijnFfGroep(j, k) : null;
      for (let h = 0; h < spec.koppen; h++) {
        const a = kop ? (kop[h] || 0) / 255 * aan : 0;
        const px = x - bw / 2 + bw * (h + 0.5) / spec.koppen;
        ctx.fillStyle = kop ? `rgba(${127 + 100 * a | 0},${224 + 20 * a | 0},${195 + 50 * a | 0},${(0.2 + 0.8 * a).toFixed(2)})` : `rgba(160,180,225,${(0.35 + 0.5 * aan).toFixed(2)})`;
        ctx.beginPath(); ctx.arc(px, ay + bh / 2, Math.max(1, bw / spec.koppen * (0.2 + 0.12 * a)), 0, 7); ctx.fill();
      }
      const st = ffg ? ffg.length : 24;
      for (let i = 0; i < st; i++) {
        const a = ffg ? (ffg[i] || 0) / 255 * aan : 0;
        ctx.fillStyle = ffg ? `rgba(${127 + 100 * a | 0},${224 + 20 * a | 0},${195 + 50 * a | 0},${(0.15 + 0.85 * a).toFixed(2)})` : `rgba(160,180,225,${(0.2 + 0.4 * aan).toFixed(2)})`;
        ctx.fillRect(x - bw / 2 + bw * (i + 0.5) / st, fy + bh * 0.25, Math.max(1, DPR * 0.8), bh * 0.5);
      }
      // de lussen van de stroom door de bouw heen
      ctx.strokeStyle = `rgba(120,140,190,${(0.18 + 0.3 * aan).toFixed(2)})`;
      ctx.beginPath(); ctx.moveTo(x, P.stroomY - P.stroomH / 2); ctx.lineTo(x, ay + bh); ctx.moveTo(x, P.stroomY + P.stroomH / 2); ctx.lineTo(x, fy); ctx.stroke();
    }
  }
  // namen onder de lagen, waar ze passen
  ctx.font = mono; ctx.textBaseline = "top"; ctx.textAlign = "center";
  const om = Math.max(1, Math.ceil(fs * 6.2 / P.stapX));
  const nyb = P.stroomY + P.stroomH / 2 + fs * 3.4;
  for (let k = 0; k < n; k++) {
    if (om > 1 && k % om !== 0 && k !== n - 1) continue;
    const [a, b] = NAMEN[k] || ["", ""], x = laagX(k);
    const licht = laagBijMuis() === k;
    ctx.fillStyle = licht ? "rgba(234,238,247,1)" : "rgba(234,238,247,0.75)"; ctx.fillText(a, x, nyb);
    if (om === 1 || k === 0 || k === n - 1) { ctx.fillStyle = kleurVan(b); ctx.fillText(b, x, nyb + fs * 1.3); }
  }
  // aanwijzen: de laag licht op
  const hk = laagBijMuis();
  if (hk !== null) {
    ctx.strokeStyle = "rgba(234,238,247,0.35)"; ctx.lineWidth = 1;
    rondRect(ctx, laagX(hk) - P.stapX * 0.45, P.boven, P.stapX * 0.9, H - P.boven - P.onder, 6 * DPR); ctx.stroke();
  }
  ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
  ctx.globalAlpha = 1;
}

/* ---- de laag open: kanalen, matrices, bouw ---- */
function tekenLaag(t, j, alpha) {
  const k = zoom.laag; if (k === null) return;
  const fs = P.fs, mono = `500 ${fs}px "JetBrains Mono", ui-monospace, Consolas, monospace`;
  ctx.globalAlpha = alpha;
  ctx.fillStyle = "rgba(10,14,28,0.92)"; ctx.fillRect(0, 0, B, H);
  const [naam, soort] = NAMEN[k] || ["", ""];
  // kop: terug, naam, pijltjes
  ctx.font = mono; ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
  ctx.fillStyle = "rgba(142,153,179,0.95)"; ctx.fillText("← terug (Esc)", fs * 1.2, fs * 2);
  ctx.font = `700 ${fs * 1.5}px "JetBrains Mono", ui-monospace, monospace`; ctx.fillStyle = "rgba(234,238,247,0.95)";
  ctx.fillText(naam, fs * 12, fs * 2.1);
  ctx.font = mono; ctx.fillStyle = kleurVan(soort); ctx.fillText(soort, fs * 12 + naam.length * fs * 0.95 + fs, fs * 2.05);
  ctx.fillStyle = "rgba(92,103,129,0.9)"; ctx.textAlign = "right"; ctx.fillText("← → andere laag", B - fs * 1.2, fs * 2); ctx.textAlign = "left";

  const top = fs * 3.6, hoog = H - top - fs * 3.2;
  const rij = (j >= 0 && rijen[j]) ? rijen[j] : null, v = rij ? (rij[k] || []) : [], m = kolMax[k];
  // links: de kanalen als raster 24 x 16 (of de ene uitvoerknoop)
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
      if (muis && muis.x >= x && muis.x < x + cel && muis.y >= y && muis.y < y + cel) aanw = `kanaal ${c}${kan ? "" : ` (groep ${g})`} · activiteit ${(a * 100).toFixed(0)}% van het max van deze laag`;
    }
    // de feedforward: 1536 eenheden als raster 48 x 32, gemiddeld over deze gedachte
    if (ffe && ffe.length) {
      const fcel = Math.min(rasterB / 48, (hoog - rasterH - fs * 3.6) / 32), fy0 = ry + rasterH + fs * 2.2;
      ctx.fillStyle = "rgba(92,103,129,0.9)"; ctx.fillText(`${ffe.length} feedforward-eenheden · gemiddeld in deze gedachte`, rx, fy0 - fs * 0.6);
      for (let u = 0; u < ffe.length; u++) {
        const a = (ffe[u] || 0) / 255, x = rx + (u % 48) * fcel, y = fy0 + Math.floor(u / 48) * fcel;
        ctx.fillStyle = `rgba(${127 + 100 * a | 0},${224 + 20 * a | 0},${195 + 50 * a | 0},${(0.1 + 0.9 * a * a).toFixed(3)})`;
        ctx.fillRect(x + 0.5, y + 0.5, Math.max(0.5, fcel - 1), Math.max(0.5, fcel - 1));
        if (muis && muis.x >= x && muis.x < x + fcel && muis.y >= y && muis.y < y + fcel) aanw = `feedforward-eenheid ${u} · gemiddeld ${(a * 100).toFixed(0)}% van het max in deze laag`;
      }
    }
  }
  // midden: de matrix naar de volgende laag
  const mx = rx + rasterB + fs * 2.5, mB = Math.min(B - mx - fs * 12.5, hoog * 0.9), mcel = mB / 32, my = top + (hoog - mB) / 2;
  const M = (k < KOL.length - 2 && bedrading) ? bedrading[k] : null;
  ctx.fillStyle = "rgba(92,103,129,0.9)";
  if (M) {
    ctx.fillText(`bedrading naar ${NAMEN[k + 1][0]} · 32 × 32 groepen · ${"mint"} plus, ${"koraal"} min`, mx, my - fs * 0.8);
    for (let d = 0; d < 32; d++) for (let b = 0; b < 32; b++) {
      const w = M[d] ? (M[d][b] || 0) : 0, x = mx + b * mcel, y = my + d * mcel;
      ctx.fillStyle = warm(w); ctx.fillRect(x + 0.5, y + 0.5, mcel - 1, mcel - 1);
      if (muis && muis.x >= x && muis.x < x + mcel && muis.y >= y && muis.y < y + mcel) aanw = `van groep ${b} (${NAMEN[k][0]}) naar groep ${d} (${NAMEN[k + 1][0]}): ${w >= 0 ? "+" : ""}${w.toFixed(3)}`;
    }
    ctx.fillStyle = "rgba(92,103,129,0.8)"; ctx.textAlign = "left";
    ctx.fillText("bron →", mx, my + mB + fs * 1.2); ctx.save(); ctx.translate(mx - fs * 0.6, my + mB); ctx.rotate(-Math.PI / 2); ctx.fillText("doel →", 0, 0); ctx.restore();
  } else if (k === KOL.length - 2 && bedradingUit) {
    ctx.fillText("bedrading naar de uitvoer · per groep", mx, my - fs * 0.8);
    const bw = mB / 32;
    for (let b = 0; b < 32; b++) { const w = bedradingUit[b] || 0, h = Math.abs(w) * mB * 0.9; ctx.fillStyle = warm(w); ctx.fillRect(mx + b * bw + 1, my + mB - h, bw - 2, h);
      if (muis && muis.x >= mx + b * bw && muis.x < mx + (b + 1) * bw && muis.y >= my && muis.y < my + mB) aanw = `groep ${b} → uitvoer: ${w >= 0 ? "+" : ""}${w.toFixed(3)}`; }
  } else {
    ctx.fillText(k === KOL.length - 1 ? "de uitvoer: hier wordt haar antwoord een teken" : "de inbedding: tekens worden 384 getallen", mx, my - fs * 0.8);
  }
  // rechts: de bouw van deze laag
  const bx = B - fs * 10.5, by = top + fs * 0.4;
  ctx.fillStyle = "rgba(92,103,129,0.9)"; ctx.fillText("de bouw", bx, by);
  const regels = KOL[k] === 1 ? [["uitvoer", "1 knoop"], ["zekerheid", "softmax"]] : k === 0 ? [["inbedding", `${spec.breedte}`], ["positie", "rotatie"]] :
    [["aandacht", `${spec.koppen} koppen × 64`], ["feedforward", `${spec.verborgen} eenheden`], ["stroom", `${spec.breedte} kanalen`], ["normalisatie", "2×"]];
  ctx.font = mono;
  regels.forEach(([a, b], i) => { const y = by + fs * 2.3 * (i + 1); ctx.fillStyle = "rgba(234,238,247,0.85)"; ctx.fillText(a, bx, y); ctx.fillStyle = "rgba(142,153,179,0.95)"; ctx.fillText(b, bx, y + fs * 1.05); });
  // de koppen, nu: zes staven
  if (kopv) {
    const ky = by + fs * 2.3 * (regels.length + 1) + fs * 2.6, kw = fs * 8;
    ctx.fillStyle = "rgba(92,103,129,0.9)"; ctx.fillText(`${kopv.length} koppen · nu`, bx, ky - fs * 0.6);
    kopv.forEach((val, h) => {
      const a = (val || 0) / 255, y = ky + h * fs * 1.15;
      ctx.fillStyle = "rgba(21,28,48,1)"; ctx.fillRect(bx, y, kw, fs * 0.75);
      ctx.fillStyle = `rgba(${127 + 100 * a | 0},${224 + 20 * a | 0},${195 + 50 * a | 0},0.9)`; ctx.fillRect(bx, y, kw * a, fs * 0.75);
      if (muis && muis.x >= bx && muis.x < bx + kw && muis.y >= y && muis.y < y + fs * 0.75) aanw = `kop ${h + 1} · activiteit nu ${(a * 100).toFixed(0)}% van het max van deze laag`;
    });
  }
  // de laagnaam-meting (van de kijker): welke familie deze laag het meest laat oplichten
  const ln = (stand && Array.isArray(stand.laagnamen)) ? stand.laagnamen.find(x => x && x.laag === k) : null;
  if (ln && ln.sterkte) { const ny = by + fs * 2.3 * (regels.length + 1) + (kopv ? fs * 2.6 + kopv.length * fs * 1.15 + fs * 1.2 : 0); ctx.fillStyle = "rgba(92,103,129,0.9)"; ctx.fillText(`naam uit de meting:`, bx, ny); ctx.fillStyle = kleurVan(ln.naam); ctx.fillText(`${ln.naam} (${(+ln.sterkte).toFixed(2)}×)`, bx, ny + fs * 1.05); }
  // onderin: wat je aanwijst
  ctx.fillStyle = aanw ? "rgba(234,238,247,0.95)" : "rgba(92,103,129,0.8)"; ctx.textAlign = "left";
  ctx.fillText(aanw || "wijs een kanaal of een vakje aan", fs * 1.2, H - fs * 1.2);
  ctx.globalAlpha = 1;
}

/* ---- elk beeld ---- */
function teken(t) {
  ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
  ctx.clearRect(0, 0, B, H);
  if (!rijen.length && wachtrij.length) nieuweGedachte(t);
  const n = rijen.length, fs = P.fs, mono = `500 ${fs}px "JetBrains Mono", ui-monospace, Consolas, monospace`;
  let j = -1, veeg = 0;
  if (n) {
    const u = (t - speelStart) / 1000 / TEKEN_S;
    j = Math.min(n - 1, Math.floor(u)); veeg = Math.min(1, (u - Math.floor(u)) / VEEG);
    if (j >= n - 1 && !klaarSinds && (u - (n - 1)) > 1) klaarSinds = t;
    if (j >= n - 1 && klaarSinds) veeg = 1;
    antwoordNu = Math.max(0, Math.min(antwoordDoel.length, j));
    if (t - laatstTonen > 80) { laatstTonen = t; document.getElementById("antwoord").textContent = antwoordDoel.slice(0, antwoordNu); }
  }
  // de zoom glijdt
  zoom.t += ((zoom.doel || 0) - zoom.t) * 0.12;
  if (Math.abs(zoom.t - (zoom.doel || 0)) < 0.002) zoom.t = zoom.doel || 0;
  if (zoom.t < 0.999) tekenOverzicht(t, j, veeg, 1 - zoom.t);
  if (zoom.t > 0.001 && zoom.laag !== null) tekenLaag(t, j, zoom.t);

  // bovenaan: wat ze schrijft (in beide standen)
  ctx.font = mono; ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
  if (zoom.t < 0.5) {
    ctx.fillStyle = "rgba(92,103,129,0.9)";
    ctx.fillText(n ? (j === 0 ? "ze leest de vraag" : (j < n - 1 ? "ze schrijft" : "klaar — haar gedachte blijft staan")) : "wachten op een gedachte…", P.links, fs * 1.6);
    if (n && j > 0) { ctx.fillStyle = "rgba(234,238,247,0.9)"; ctx.fillText(antwoordDoel.slice(0, j).slice(-70), P.links + fs * 11, fs * 1.6); }
    ctx.fillStyle = "rgba(92,103,129,0.8)"; ctx.textAlign = "right"; ctx.fillText("klik op een laag om hem te openen", B - P.rechts, fs * 1.6); ctx.textAlign = "left";
  }
  if (n && klaarSinds && t - klaarSinds > 7000) { if (wachtrij.length) nieuweGedachte(t); else { speelStart = t; klaarSinds = 0; } }
  requestAnimationFrame(teken);
}
requestAnimationFrame(teken);
