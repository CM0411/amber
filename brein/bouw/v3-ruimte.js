/* ======================================================================
   De Sterrenwacht — Claudes ontwerp, van de grond af (24 aug 2026, Cley:
   "begin vanaf nul tot je eigen futuristische design").

   Geen website met bladen. Eén scherm. Haar brein in het midden, naar
   Cleys vierde afbeelding (24 aug laat: "precies dit en niet anders"):
   links drie datastromen als bits -- haar vraag (cyaan), wat ze zich
   herinnert (magenta) en wat ze tot nu toe schreef (geel) -- die als
   gekleurde vezels samenkomen in één kolom: de 32 groepen van haar
   inbedding. Rechts een blok van enen en nullen: haar 20 lagen x 384
   kanalen, 1 = actief (boven de helft van het max van die laag), 0 =
   stil, de kleur is hoe sterk. Live per teken. Niets schuift, niets
   flitst: elke cel glijdt naar zijn waarde. Elke knoop is echt: een groep van 12 kanalen
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
    const r = await fetch("/rapport/fijn.json?t=" + tijd, {cache: "no-store"});
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

/* ---- de vorm: stromen, kolom, blok ---- */
let vorm = [], glad = [], gladKan = [];  // per station {k, n, soort}; glad: groepen; gladKan: kanalen (getoond, glijdend)
let liveKanaal = null;                   // live.json: per laag 384 cijfers 0..9
let samen = [];
function bouwVorm() {
  vorm = KOL.map((n, k) => ({k, n, soort: n === 1 ? "uit" : (k === 0 ? "in" : "laag")}));
  glad = KOL.map(n => new Float32Array(n));
  gladKan = KOL.map(() => new Float32Array(spec.breedte));
  vuil = true;
}
function bouwSamen() {}
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

/* ---- de maten van het beeld ---- */
const TINT = {cyaan: "41,211,255", magenta: "255,63,160", geel: "255,210,63", blauw: "70,120,255"};
const STROOM = [["vraag", TINT.cyaan], ["herinnering", TINT.magenta], ["antwoord", TINT.geel]];
const NIVO = ["rgba(60,95,200,0.55)", "rgba(80,150,255,0.85)", "rgba(41,211,255,0.95)", "rgba(120,235,255,1)", "rgba(255,63,160,1)", "rgba(255,210,63,1)"];
const G = {};
let vonken = [];                         // vonkjes over de vezels (als in het weefsel): bij elk nieuw teken, klein, kort
function vonk(t) {
  if (RUSTIG || !G.cel) return;
  const g0 = glad[0] || [], nk = KOL[0];
  for (let i = 0; i < 3; i++) for (let v = 0; v < 2; v++) {
    let g = Math.floor(rnd((t | 0) * 7 + i * 31 + v * 13) * nk);
    for (let p = 0; p < 6 && (g0[g] || 0) < 0.4; p++) g = Math.floor(rnd((t | 0) * 7 + i * 31 + v * 13 + p * 101) * nk);   // liever een actieve groep
    vonken.push({i, g, t0: t + v * 90, duur: 650});
  }
  if (vonken.length > 120) vonken = vonken.slice(-120);
}
function rnd(seed) { let t = (seed | 0) + 0x6D2B79F5; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; }
let vuil = true, laatstBediend = 0;
const atlas = document.createElement("canvas"), blokDoek = document.createElement("canvas");
let blokTik = 0;
function projecteer() {
  const L = P.vrijX, T = P.vrijY, W = P.vrijB, Hh = P.vrijH, fs = P.fs, lagen = Math.max(1, KOL.length - 2);
  G.rijen = 6; G.kolommen = Math.ceil(spec.breedte / G.rijen);
  const rows = lagen * G.rijen + (lagen - 1);
  G.cel = Math.max(2, Math.min((W * 0.55) / G.kolommen, (Hh - fs * 7.5) / rows));   // onderin ruimte voor de tegels en het onderschrift
  G.blokB = G.cel * G.kolommen; G.blokH = G.cel * rows;
  G.blokX = L + W - G.blokB - fs * 4.2; G.blokY = T + fs * 1.6 + (Hh - fs * 7.5 - G.blokH) / 2;
  G.kolX = G.blokX - fs * 3.2; G.kolY0 = G.blokY + G.blokH * 0.2; G.kolY1 = G.blokY + G.blokH * 0.8;
  G.stroomX0 = L + fs * 0.6; G.stroomX1 = G.kolX - fs * 10;
  G.stroomY = [T + Hh * 0.32, T + Hh * 0.5, T + Hh * 0.68];
  // de letters 0 en 1 in zes sterktes, één keer getekend
  const c = G.cel;
  atlas.width = Math.ceil(c * 12); atlas.height = Math.ceil(c);
  const q = atlas.getContext("2d");
  q.clearRect(0, 0, atlas.width, atlas.height);
  q.font = `700 ${Math.max(2, c * 1.05)}px "JetBrains Mono", ui-monospace, monospace`; q.textAlign = "center"; q.textBaseline = "middle";
  for (let n = 0; n < 6; n++) for (let g = 0; g < 2; g++) { q.fillStyle = NIVO[n]; q.fillText(String(g), (n * 2 + g) * c + c / 2, c / 2 + c * 0.05); }
  blokDoek.width = Math.ceil(G.blokB); blokDoek.height = Math.ceil(G.blokH);
  vuil = false; blokTik = 0;
}
const bits = s => { let u = ""; for (const b of new TextEncoder().encode(s || "")) u += b.toString(2).padStart(8, "0"); return u; };

/* ---- bediening: aanwijzen en klikken in het blok ---- */
let sleep = null, hover = {station: null, kanaal: null};
function schermXY(e) { const r = doek.getBoundingClientRect(); const p = e.touches ? e.touches[0] : e; return {x: (p.clientX - r.left) * DPR, y: (p.clientY - r.top) * DPR}; }
doek.addEventListener("pointermove", e => { muis = schermXY(e); laatstBediend = performance.now(); });
doek.addEventListener("pointerleave", () => { muis = null; hover = {station: null, kanaal: null}; });
doek.addEventListener("pointerup", e => {
  const p = schermXY(e);
  if (zoom.t < 0.5) { zoekHover(); if (hover.station !== null) openLaag(hover.station); }
  else if (p.y - P.boven < P.fs * 3.2 && p.x < P.fs * 9) sluit();
});
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
  if (!muis || zoom.t > 0.5 || !G.cel) return;
  if (muis.x >= G.blokX && muis.x < G.blokX + G.blokB && muis.y >= G.blokY && muis.y < G.blokY + G.blokH) {
    const per = G.rijen + 1, rij = Math.floor((muis.y - G.blokY) / G.cel), k = Math.floor(rij / per) + 1, r = rij % per;
    if (r < G.rijen && k >= 1 && k <= KOL.length - 2) { hover.station = k; hover.kanaal = Math.min(spec.breedte - 1, r * G.kolommen + Math.floor((muis.x - G.blokX) / G.cel)); }
  } else if (Math.abs(muis.x - G.kolX) < P.fs * 1.5 && muis.y >= G.kolY0 - P.fs && muis.y <= G.kolY1 + P.fs) hover.station = 0;
}

/* ---- helpers ---- */
function rondRect(q, x, y, w, h, r) { q.beginPath(); q.moveTo(x + r, y); q.arcTo(x + w, y, x + w, y + h, r); q.arcTo(x + w, y + h, x, y + h, r); q.arcTo(x, y + h, x, y, r); q.arcTo(x, y, x + w, y, r); q.closePath(); }
function warm(v) {                       // gewicht -> kleur (de microscoop): cyaan plus, magenta min
  const a = Math.min(1, Math.abs(v));
  return v >= 0 ? `rgba(41,211,255,${(0.08 + 0.92 * a).toFixed(3)})` : `rgba(255,63,160,${(0.08 + 0.92 * a).toFixed(3)})`;
}
function activiteitVan(j, k, i) {         // een groep in doorgang j: 0..1 ten opzichte van het maximum van die laag in deze gedachte
  const rij = rijen[j]; if (!rij) return 0;
  return Math.min(1, ((rij[k] || [])[i] || 0) / kolMax[k]);
}
function activiteitKanaal(k, c) { return gladKan[k] ? gladKan[k][c] : 0; }
function doelKanalen(j, k) {              // 384 doelwaarden 0..1 voor laag k: live (per teken), anders fijn.json, anders de groepen
  const n = spec.breedte, uit = new Float32Array(n);
  const s = LIVE && liveKanaal && liveKanaal[k - 1];
  if (s && s.length >= n) { for (let c = 0; c < n; c++) uit[c] = (s.charCodeAt(c) - 48) / 9; return uit; }
  const kan = fijnKanaal(j, k);
  if (kan) { for (let c = 0; c < n; c++) uit[c] = (kan[c] || 0) / 255; return uit; }
  const rij = rijen[j]; if (!rij) return uit;
  const per = Math.max(1, Math.floor(n / Math.max(1, KOL[k])));
  for (let c = 0; c < n; c++) uit[c] = Math.min(1, ((rij[k] || [])[Math.min(KOL[k] - 1, Math.floor(c / per))] || 0) / kolMax[k]);
  return uit;
}
const nivo = v => v < 0.25 ? 0 : v < 0.5 ? 1 : v < 0.7 ? 2 : v < 0.85 ? 3 : v < 0.95 ? 4 : 5;

/* ---- het blok: 20 lagen x 384 kanalen als enen en nullen (tien keer per seconde ververst, glijdend) ---- */
function tekenBlok(j) {
  const q = blokDoek.getContext("2d"), c = G.cel, lagen = KOL.length - 2;
  q.clearRect(0, 0, blokDoek.width, blokDoek.height);
  for (let k = 1; k <= lagen; k++) {
    const doel = doelKanalen(j, k), g = gladKan[k]; if (!g) continue;
    const y0 = (k - 1) * (G.rijen + 1) * c;
    for (let ch = 0; ch < spec.breedte; ch++) {
      g[ch] += (doel[ch] - g[ch]) * 0.35;
      const v = g[ch], n = nivo(v), een = v >= 0.5 ? 1 : 0;
      q.drawImage(atlas, (n * 2 + een) * c, 0, c, c, (ch % G.kolommen) * c, y0 + Math.floor(ch / G.kolommen) * c, c, c);
    }
  }
}

/* ---- de ruimte: elk beeld ---- */
function tekenRuimte(t, j, veeg, alpha) {
  if (vuil || !G.cel) projecteer();
  ctx.globalAlpha = alpha;
  const rij = (j >= 0 && rijen[j]) ? rijen[j] : null, n = KOL.length, fs = P.fs;
  const mono = `500 ${fs * 0.8}px "JetBrains Mono", ui-monospace, monospace`;
  for (let k = 0; k < n; k++) { const g = glad[k]; if (!g) continue; for (let i = 0; i < g.length; i++) { const doel = rij ? activiteitVan(j, k, i) : 0; g[i] += (doel - g[i]) * 0.12; } }
  if (t - blokTik > 100) { blokTik = t; tekenBlok(j); }
  // de drie stromen: bits van haar vraag, haar herinnering en wat ze tot nu toe schreef
  const bron = [stand ? (stand.opgave || "") : "", (stand && stand.herinnert && stand.herinnert[0]) ? (stand.herinnert[0].opgave || "") : "", antwoordDoel.slice(0, Math.max(0, antwoordNu))];
  ctx.font = `500 ${fs * 0.72}px "JetBrains Mono", ui-monospace, monospace`; ctx.textBaseline = "middle"; ctx.textAlign = "left";
  const bitB = ctx.measureText("0").width, past = Math.max(8, Math.floor((G.stroomX1 - G.stroomX0) / bitB));
  STROOM.forEach(([naam, kl], i) => {
    const y = G.stroomY[i], b = bits(bron[i]), staart = b.slice(-past);
    ctx.fillStyle = `rgba(${kl},0.9)`; ctx.font = `700 ${fs * 0.62}px "JetBrains Mono", ui-monospace, monospace`;
    ctx.fillText(naam.toUpperCase() + (bron[i] ? "" : " · nog niets"), G.stroomX0, y - fs * 1.05);
    ctx.font = `500 ${fs * 0.72}px "JetBrains Mono", ui-monospace, monospace`;
    for (let p = 0; p < staart.length; p++) { const u = (p + 1) / staart.length, nieuw = p >= staart.length - 8; ctx.fillStyle = nieuw ? "rgba(255,255,255,0.95)" : `rgba(${kl},${(0.25 + 0.7 * u).toFixed(2)})`; ctx.fillText(staart[p], G.stroomX0 + p * bitB, y); }
  });
  // de vezels: van elke stroom naar elke groep van de inbedding, licht naar de activiteit van die groep
  const g0 = glad[0] || [], nk = KOL[0];
  ctx.lineCap = "round";
  for (let i = 0; i < 3; i++) {
    const x0 = G.stroomX1 + fs * 0.4, y0 = G.stroomY[i], kl = STROOM[i][1];
    for (let g = 0; g < nk; g++) {
      const y1 = G.kolY0 + (G.kolY1 - G.kolY0) * (nk > 1 ? g / (nk - 1) : 0.5), a = g0[g] || 0, mx = (x0 + G.kolX) / 2;
      ctx.strokeStyle = `rgba(${kl},${(0.10 + 0.6 * a).toFixed(3)})`; ctx.lineWidth = DPR * (0.5 + 1.0 * a);
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.bezierCurveTo(mx, y0, mx, y1, G.kolX - DPR * 4, y1); ctx.stroke();
    }
  }
  // de vonkjes: over de vezel van de stroom naar de groep, dan door naar het blok
  const nu = performance.now();
  vonken = vonken.filter(v => nu - v.t0 < v.duur + 300);
  for (const v of vonken) {
    const u = (nu - v.t0) / v.duur; if (u < 0) continue;
    const kl = STROOM[v.i][1], x0 = G.stroomX1 + fs * 0.4, y0 = G.stroomY[v.i], y1 = G.kolY0 + (G.kolY1 - G.kolY0) * (nk > 1 ? v.g / (nk - 1) : 0.5), mx = (x0 + G.kolX) / 2, x3 = G.kolX - DPR * 4;
    let x, y, a;
    if (u <= 1) { const w = 1 - u; x = w * w * w * x0 + 3 * w * w * u * mx + 3 * w * u * u * mx + u * u * u * x3; y = w * w * w * y0 + 3 * w * w * u * y0 + 3 * w * u * u * y1 + u * u * u * y1; a = 0.95; }
    else { const u2 = Math.min(1, (u - 1) * v.duur / 300), yb = G.blokY + G.blokH * (nk > 1 ? v.g / (nk - 1) : 0.5); x = G.kolX + DPR * 6 + (G.blokX - DPR * 3 - G.kolX - DPR * 6) * u2; y = y1 + (yb - y1) * u2; a = 0.9 * (1 - u2); }
    ctx.fillStyle = `rgba(${kl},${a.toFixed(2)})`; ctx.beginPath(); ctx.arc(x, y, DPR * 2.2, 0, 7); ctx.fill();
    ctx.fillStyle = "rgba(255,255,255," + (0.6 * a).toFixed(2) + ")"; ctx.beginPath(); ctx.arc(x, y, DPR * 1.0, 0, 7); ctx.fill();
  }
  // de kolom: de 32 groepen van de inbedding, en de streepjes naar het blok
  for (let g = 0; g < nk; g++) {
    const y = G.kolY0 + (G.kolY1 - G.kolY0) * (nk > 1 ? g / (nk - 1) : 0.5), a = g0[g] || 0;
    ctx.fillStyle = NIVO[nivo(a)]; ctx.beginPath(); ctx.arc(G.kolX, y, DPR * (2.2 + 1.6 * a), 0, 7); ctx.fill();
    const yb = G.blokY + G.blokH * (nk > 1 ? g / (nk - 1) : 0.5);
    ctx.strokeStyle = `rgba(${TINT.blauw},${(0.15 + 0.5 * a).toFixed(2)})`; ctx.lineWidth = DPR;
    ctx.beginPath(); ctx.moveTo(G.kolX + DPR * 6, y); ctx.lineTo(G.blokX - DPR * 3, yb); ctx.stroke();
  }
  if (hover.station === 0) { ctx.strokeStyle = "rgba(255,255,255,0.8)"; ctx.lineWidth = DPR; rondRect(ctx, G.kolX - fs, G.kolY0 - fs * 0.8, fs * 2, G.kolY1 - G.kolY0 + fs * 1.6, 4 * DPR); ctx.stroke(); }
  // het blok
  ctx.drawImage(blokDoek, G.blokX, G.blokY);
  // de lagen erlangs, en de aangewezen laag/het aangewezen kanaal
  ctx.font = `700 ${fs * 0.62}px "JetBrains Mono", ui-monospace, monospace`; ctx.textAlign = "left"; ctx.textBaseline = "middle";
  for (let k = 1; k <= n - 2; k++) {
    const y = G.blokY + ((k - 1) * (G.rijen + 1) + G.rijen / 2) * G.cel, licht = hover.station === k || (zoom.laag === k && zoom.doel);
    ctx.fillStyle = licht ? "rgba(255,255,255,0.95)" : `rgba(${TINT.cyaan},0.7)`;
    ctx.fillText(`L${k}`, G.blokX + G.blokB + fs * 0.5, y);
    if (licht) { ctx.strokeStyle = "rgba(255,255,255,0.7)"; ctx.lineWidth = DPR; ctx.strokeRect(G.blokX - DPR, G.blokY + (k - 1) * (G.rijen + 1) * G.cel - DPR, G.blokB + 2 * DPR, G.rijen * G.cel + 2 * DPR); }
  }
  if (hover.station !== null && hover.kanaal !== null) {
    const k = hover.station, ch = hover.kanaal, x = G.blokX + (ch % G.kolommen) * G.cel, y = G.blokY + ((k - 1) * (G.rijen + 1) + Math.floor(ch / G.kolommen)) * G.cel;
    ctx.strokeStyle = "rgba(255,255,255,0.95)"; ctx.lineWidth = DPR; ctx.strokeRect(x - DPR, y - DPR, G.cel + 2 * DPR, G.cel + 2 * DPR);
  }
  // de uitvoer: haar zekerheid over het teken van nu, rechtsonder het blok
  const zeker = glad[n - 1] ? glad[n - 1][0] : 0;
  ctx.fillStyle = `rgba(${TINT.geel},0.85)`; ctx.font = `700 ${fs * 0.62}px "JetBrains Mono", ui-monospace, monospace`; ctx.textAlign = "right";
  ctx.fillText(`UITVOER · zekerheid ${Math.round(100 * zeker)}%`, G.blokX + G.blokB, G.blokY + G.blokH + fs * 1.0);
  ctx.fillStyle = `rgba(${TINT.cyaan},0.7)`; ctx.textAlign = "left";
  ctx.fillText(`${n - 2} LAGEN × ${spec.breedte} KANALEN · 1 = ACTIEF, 0 = STIL · KLEUR = STERKTE`, G.blokX, G.blokY - fs * 0.9);
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
  doek.style.cursor = (hover.station !== null || zoom.t > 0.5) ? "pointer" : "default";
  if (t - laatstMeld > 100) { laatstMeld = t; if (typeof toonOnderschrift === "function") toonOnderschrift(j, n); }
  if (!LIVE && n && vast === null && klaarSinds && t - klaarSinds > 7000) { if (wachtrij.length) nieuweGedachte(t); else { speelStart = t; klaarSinds = 0; } }
  if (!FOTO || ++beelden < 40) requestAnimationFrame(teken);
}
requestAnimationFrame(teken);
