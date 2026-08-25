/* ======================================================================
   De Sterrenwacht — de waaier (25 aug 2026, naar Cleys clip: "illustrative
   3d animation neural network, wide view").

   Links één lichtpunt: haar vraag. Daaruit waaieren draden naar de 32
   groepen van haar inbedding, en van elke kolom naar de volgende: 20 lagen,
   32 groepen per laag, 21 kolommen naast elkaar, steeds een beetje hoger,
   zoals in de clip. Elke draad is echt: het gewicht van groep naar groep
   uit stand.json (de bedrading). Een draad licht alleen op als er nú iets
   doorheen loopt: groep ervoor actief × gewicht × groep erna actief, per
   geschreven teken gemeten (live.json, elke 0,1 s). Rechts de uitvoer:
   haar zekerheid. (De bits-kolom ging er 25 aug 's avonds weer af, op Cleys woord.)
   Alleen blauw. Geen puls over het scherm: de vonkjes lopen over de draad
   waar het signaal loopt. Bij het openen bouwt het netwerk zich één keer
   op van links naar rechts, daarna staat het. Klik op een knoop of een
   laagnaam en de microscoop van die laag gaat open.
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
let LIVE = false, herhaal = false, herhaalJ = 0;                        // live: het beeld volgt de laatste doorgang uit live.json
const RUSTIG = matchMedia("(prefers-reduced-motion: reduce)").matches;
const FOTO = /foto=1/.test(location.search);        // proefopname: geen opbouw, na 40 beelden stoppen

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

/* ---- maat: het doek is het hele scherm; de waaier zit in het vrije midden ---- */
const P = {fs: 12, boven: 0, vrijX: 0, vrijY: 0, vrijB: 1, vrijH: 1};
function maat() {
  if (!doek.clientWidth) return;
  const nb = Math.round(doek.clientWidth * DPR), nh = Math.round(doek.clientHeight * DPR);
  if (nb !== doek.width) doek.width = nb;   // alleen als het echt anders is: op maat zetten wist het doek
  if (nh !== doek.height) doek.height = nh;
  if (nb !== stil.width) stil.width = nb;
  if (nh !== stil.height) stil.height = nh;
  B = nb; H = nh;
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

/* ---- de vorm: kolommen van groepen, en de stroom door elke draad ---- */
let vorm = [], glad = [], gladKan = [];  // per station {k, n, soort}; glad: groepen (glijdend); gladKan: kanalen (voor de microscoop en het aanwijzen)
let liveKanaal = null;                   // live.json: per laag 384 cijfers 0..9
let samen = [];
let stroom = [], stroomIn = null, stroomUit = null, wMax = [];   // per tussenruimte: de stroom door elke draad, 0..1 (glijdend)
function bouwVorm() {
  vorm = KOL.map((n, k) => ({k, n, soort: n === 1 ? "uit" : (k === 0 ? "in" : "laag")}));
  const anders = glad.length !== KOL.length || KOL.some((n, k) => glad[k].length !== n);
  if (anders) {                          // alleen opnieuw als de vorm echt anders is: anders zou alles even doven
    glad = KOL.map(n => new Float32Array(n));
    gladKan = KOL.map(() => new Float32Array(spec.breedte));
    stroom = []; for (let c = 0; c + 2 < KOL.length; c++) stroom.push(new Float32Array(KOL[c] * Math.min(K_PER_GROEP, KOL[c + 1]) * 4));   // ruim: de paren zijn hooguit K per doelgroep
    stroomIn = new Float32Array(KOL[0]); stroomUit = new Float32Array(KOL[KOL.length - 2]);
  }
  wMax = []; for (let c = 0; c + 2 < KOL.length; c++) { let m = 0.0001; const M = bedrading && bedrading[c]; if (M) for (const r of M) for (const v of r) m = Math.max(m, Math.abs(v)); wMax.push(m); }
  wMaxUit = 0.0001; if (bedradingUit) for (const v of bedradingUit) wMaxUit = Math.max(wMaxUit, Math.abs(v));
  vuil = true;
}
let wMaxUit = 0.0001;
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

/* ---- kleur: alleen blauw, zoals in de clip ---- */
const TINT = {draad: "150,190,255", licht: "190,220,255", knoop: "120,180,255", wit: "255,255,255", blauw: "70,120,255", cyaan: "41,211,255",
              plus: "127,224,195", min: "255,154,122"};   // 25 aug, Cley: "groen en rood, zoals bij het weefsel" -- groen is plus, rood is min
const tekenKleur = t => t > 0 ? TINT.plus : t < 0 ? TINT.min : TINT.licht;
const NIVO = ["rgba(60,95,200,0.55)", "rgba(80,150,255,0.85)", "rgba(110,190,255,0.95)", "rgba(150,215,255,1)", "rgba(200,235,255,1)", "rgba(255,255,255,1)"];
const nivo = v => v < 0.25 ? 0 : v < 0.5 ? 1 : v < 0.7 ? 2 : v < 0.85 ? 3 : v < 0.95 ? 4 : 5;
const G = {};
const pt = (u, v) => G.staand ? [v, u] : [u, v];           // u: langs de stroom (links->rechts, op de telefoon boven->onder); v: dwars
function rnd(seed) { let t = (seed | 0) + 0x6D2B79F5; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; }
let vuil = true, laatstBediend = 0;
const gloei = document.createElement("canvas");
const stil = document.createElement("canvas");            // de stille draden: een eigen laag onder het doek, één keer getekend (25 aug, Cley: "het moet heel soepel lopen")
stil.id = "doek-stil"; stil.style.cssText = "position:absolute;inset:0;width:100%;height:100%;display:block;pointer-events:none";
doek.parentNode.insertBefore(stil, doek);
let stilStijl = {clip: "", alpha: ""};
let tik = 0, vezelBron = undefined, vezelMaat = "";
let paren = [];                          // per tussenruimte: [a, b, w] van de K sterkste gewichten per doelgroep (w = |gewicht| / max van die tussenruimte)
const K_PER_GROEP = 10;
function bouwParen() {
  paren = [];
  for (let c = 0; c + 2 < KOL.length; c++) {
    const M = bedrading && bedrading[c], na = KOL[c], nb = KOL[c + 1], m = wMax[c] || 1, lijst = [];
    for (let b = 0; b < nb; b++) {
      const rij = M && M[b]; if (!rij) { for (let a = 0; a < na; a++) lijst.push([a, b, 0.3, 0]); continue; }
      const idx = []; for (let a = 0; a < na; a++) idx.push(a);
      idx.sort((x, y) => Math.abs(rij[y] || 0) - Math.abs(rij[x] || 0));
      for (let i = 0; i < Math.min(K_PER_GROEP, na); i++) lijst.push([idx[i], b, Math.abs(rij[idx[i]] || 0) / m, (rij[idx[i]] || 0) >= 0 ? 1 : -1]);
    }
    paren.push(lijst);
  }
}
let vonken = [];                         // vonkjes over de draden waar het signaal loopt
let opbouw = {t0: 0, klaar: RUSTIG || FOTO};

/* ---- de draad: van knoop naar knoop, gebogen langs de stroomas (de bundel bij de knoop, de waaier ertussen) ---- */
const BOCHT = 0.3;                        // 25 aug, Cley: "netjes aan elkaar" -- korte bundel bij de knoop, daarna bijna recht
function pad(q, a, b) {
  if (G.staand) { const d = (b[1] - a[1]) * BOCHT; q.moveTo(a[0], a[1]); q.bezierCurveTo(a[0], a[1] + d, b[0], b[1] - d, b[0], b[1]); }
  else { const d = (b[0] - a[0]) * BOCHT; q.moveTo(a[0], a[1]); q.bezierCurveTo(a[0] + d, a[1], b[0] - d, b[1], b[0], b[1]); }
}
function opPad(a, b, u) {
  const w = 1 - u; let c1, c2;
  if (G.staand) { const d = (b[1] - a[1]) * BOCHT; c1 = [a[0], a[1] + d]; c2 = [b[0], b[1] - d]; }
  else { const d = (b[0] - a[0]) * BOCHT; c1 = [a[0] + d, a[1]]; c2 = [b[0] - d, b[1]]; }
  return [w * w * w * a[0] + 3 * w * w * u * c1[0] + 3 * w * u * u * c2[0] + u * u * u * b[0],
          w * w * w * a[1] + 3 * w * w * u * c1[1] + 3 * w * u * u * c2[1] + u * u * u * b[1]];
}
function eind(c, a, b) {                 // de twee uiteinden van draad (c, a, b): c = -1 punt->inbedding, c = nK-1 laatste laag->uitvoer
  const nK = KOL.length - 1;
  if (c < 0) return [G.punt, G.knoop[0][b]];
  if (c >= nK - 1) return [G.knoop[nK - 1][a], G.uit];
  return [G.knoop[c][a], G.knoop[c + 1][b]];
}

/* ---- de maten van het beeld ---- */
function projecteer() {
  const L = P.vrijX, T = P.vrijY, W = P.vrijB, Hh = P.vrijH, fs = P.fs, nK = KOL.length - 1;
  G.staand = matchMedia("(max-width: 900px)").matches || W < Hh * 1.1;   // telefoon: de stroom loopt van boven naar onder
  const rest = G.staand ? fs * 10.5 : fs * 7.5;   // onderin #vrij staan de tegels en het onderschrift
  const uA = G.staand ? T : L, span = G.staand ? Hh - rest : W, vA = G.staand ? L : T, dwars = G.staand ? W : Hh - rest, mid = vA + dwars / 2;
  Object.assign(G, {uA, span, vA, dwars, mid, nK});
  G.punt = pt(uA + span * 0.055, mid);
  G.knoop = []; G.label = [];
  for (let c = 0; c < nK; c++) {
    const n = KOL[c], u = uA + span * (0.14 + 0.73 * c / Math.max(1, nK - 1));
    const h = dwars * (G.staand ? 0.44 + 0.46 * c / Math.max(1, nK - 1) : 0.22 + 0.42 * c / Math.max(1, nK - 1));
    const kol = []; for (let g = 0; g < n; g++) kol.push(pt(u, mid - h / 2 + (n > 1 ? h * g / (n - 1) : h / 2)));
    G.knoop.push(kol);
    G.label.push(G.staand ? pt(u, vA + fs * 0.4) : pt(u, mid + h / 2 + fs * 1.2));      // de naam: links van de rij, of onder de kolom
  }
  G.uit = pt(uA + span * 0.945, mid);
  // de gloed van een knoop in zes sterktes (een kern met een zachte hof), één keer getekend
  const R = Math.max(3, fs * (G.staand ? 0.35 : 0.45)), S = Math.ceil(R * 2); G.gloeiS = S;
  gloei.width = S * 6; gloei.height = S;
  const g2 = gloei.getContext("2d"); g2.clearRect(0, 0, gloei.width, gloei.height);
  for (let n = 0; n < 6; n++) {
    const a = n / 5, cx = n * S + S / 2, cy = S / 2;
    const hof = g2.createRadialGradient(cx, cy, 0, cx, cy, R);
    hof.addColorStop(0, `rgba(${TINT.licht},${(0.15 + 0.6 * a).toFixed(2)})`); hof.addColorStop(0.3, `rgba(${TINT.knoop},${(0.05 + 0.35 * a).toFixed(2)})`); hof.addColorStop(1, `rgba(${TINT.knoop},0)`);
    g2.fillStyle = hof; g2.fillRect(n * S, 0, S, S);
    g2.fillStyle = NIVO[n]; g2.beginPath(); g2.arc(cx, cy, DPR * (0.9 + 1.1 * a), 0, 7); g2.fill();
  }
  vuil = false; tik = 0;
}

/* ---- de stille draden: elk gewicht, één keer getekend, bleek ---- */
function bouwVezels() {
  const q = stil.getContext("2d"), nK = G.nK, BAK = 6;
  q.clearRect(0, 0, B, H); q.lineCap = "round";
  const paden = []; for (let i = 0; i < BAK; i++) paden.push(new Path2D());
  const bak = w => paden[Math.max(0, Math.min(BAK - 1, Math.floor(w * BAK)))];
  for (let g = 0; g < KOL[0]; g++) pad(paden[2], G.punt, G.knoop[0][g]);
  bouwParen();
  const padPlus = new Path2D(), padMin = new Path2D();
  for (let c = 0; c + 1 < nK; c++) for (const [a, b, w, t] of paren[c]) pad(t < 0 ? padMin : padPlus, G.knoop[c][a], G.knoop[c + 1][b]);
  for (let a = 0; a < KOL[nK - 1]; a++) pad((bedradingUit && bedradingUit[a] < 0) ? padMin : padPlus, G.knoop[nK - 1][a], G.uit);
  q.lineWidth = DPR * 0.5;                                                   // 25 aug, Cley: "de rest op 95% donkerte"
  q.strokeStyle = `rgba(${TINT.draad},${G.staand ? 0.035 : 0.05})`; paden.forEach(p => q.stroke(p));   // het punt -> de inbedding: zonder teken
  q.strokeStyle = `rgba(${TINT.plus},${G.staand ? 0.04 : 0.055})`; q.stroke(padPlus);
  q.strokeStyle = `rgba(${TINT.min},${G.staand ? 0.04 : 0.055})`; q.stroke(padMin);
  vezelBron = bedrading; vezelMaat = B + "x" + H + "|" + KOL.join(",");
}

/* ---- het licht: alleen de draden waar nú iets doorheen loopt (elk beeld, glijdend aan en uit) ---- */
const drempel = () => G.staand ? 0.6 : 0.5;    // een draad licht op vanaf 50% (telefoon: 60%) van de sterkste stroom in zijn tussenruimte
const plafond = () => G.staand ? 10 : 16;      // en per tussenruimte hooguit zoveel draden tegelijk (de sterkste)
const KS = 0.10, KA = 0.12;                    // glijsnelheid per beeld: de stroom, en het aan- en uitgaan (niets knippert, niets springt)
let tmp = new Float32Array(1024), merk = new Uint8Array(1024);
function markeer(n) { if (merk.length < n) merk = new Uint8Array(n); else merk.fill(0, 0, n); return merk; }
let lichtIn = [], lichtUit = [], lichtTussen = [];   // wat er nu aan is: groepen (in), groepen (uit), per tussenruimte de paren-indexen
let aanIn = null, aanUit = null, aanTussen = [];     // 0..1 per draad: hoe ver hij aan is
function tekenLicht() {
  if (!stroomIn || glad.length !== KOL.length) return;
  const nK = G.nK, DR = drempel(), PLAFOND = plafond(), dik = G.staand ? 0.6 : 0.85;
  if (!aanIn || aanIn.length !== stroomIn.length) aanIn = new Float32Array(stroomIn.length);
  if (!aanUit || aanUit.length !== stroomUit.length) aanUit = new Float32Array(stroomUit.length);
  ctx.lineCap = "round";
  const streep = (a, b, s, aan, t) => {    // één draad: sterkte s (boven de drempel), aan 0..1, teken t (+1 groen, -1 rood, 0 blauw)
    const f = Math.max(0, Math.min(1, (s - DR) / (1 - DR))), al = aan * (0.28 + 0.6 * f);
    if (al < 0.02) return;
    ctx.strokeStyle = `rgba(${tekenKleur(t)},${al.toFixed(3)})`; ctx.lineWidth = DPR * dik * (0.45 + 0.7 * f);
    ctx.beginPath(); pad(ctx, a, b); ctx.stroke();
    if (f > 0.85) { ctx.strokeStyle = `rgba(255,255,255,${(0.25 * aan).toFixed(3)})`; ctx.lineWidth = DPR * 0.5; ctx.stroke(); }
  };
  lichtIn = []; lichtUit = []; lichtTussen = [];
  // het punt -> de inbedding: de activiteit van de groep
  for (let g = 0; g < KOL[0]; g++) {
    const d = glad[0][g] || 0; stroomIn[g] += (d - stroomIn[g]) * KS;
    aanIn[g] += ((stroomIn[g] > DR ? 1 : 0) - aanIn[g]) * KA;
    if (aanIn[g] > 0.5) lichtIn.push(g);
    if (aanIn[g] > 0.02) streep(G.punt, G.knoop[0][g], stroomIn[g], aanIn[g], 0);
  }
  // van kolom naar kolom: groep ervoor x gewicht x groep erna, ten opzichte van de sterkste stroom in die tussenruimte
  for (let c = 0; c + 1 < nK; c++) {
    const S = stroom[c], ga = glad[c], gb = glad[c + 1], lijst = paren[c];
    if (!S || !lijst) continue;
    if (!aanTussen[c] || aanTussen[c].length !== S.length) aanTussen[c] = new Float32Array(S.length);
    const A = aanTussen[c], n = lijst.length;
    if (tmp.length < n) tmp = new Float32Array(n);
    let top = 0.000001;
    for (let i = 0; i < n; i++) { const p = lijst[i], f = (ga[p[0]] || 0) * p[2] * (gb[p[1]] || 0); tmp[i] = f; if (f > top) top = f; }
    const kand = [];
    for (let i = 0; i < n; i++) { S[i] += (tmp[i] / top - S[i]) * KS; if (S[i] > DR) kand.push(i); }
    if (kand.length > PLAFOND) kand.sort((x, y) => S[y] - S[x]).length = PLAFOND;
    const doel = markeer(n); for (const i of kand) doel[i] = 1;
    const aanLijst = [];
    for (let i = 0; i < n; i++) {
      A[i] += (doel[i] - A[i]) * KA;
      if (A[i] > 0.5) aanLijst.push(i);
      if (A[i] > 0.02) { const p = lijst[i]; streep(G.knoop[c][p[0]], G.knoop[c + 1][p[1]], S[i], A[i], p[3]); }
    }
    lichtTussen[c] = aanLijst;
  }
  // de laatste laag -> de uitvoer
  { const na = KOL[nK - 1], ga = glad[nK - 1], zeker = glad[nK] ? glad[nK][0] : 0; let top = 0.000001;
    for (let a = 0; a < na; a++) { const f = (ga[a] || 0) * (bedradingUit ? Math.abs(bedradingUit[a] || 0) / wMaxUit : 0.3) * Math.max(0.2, zeker); tmp[a] = f; if (f > top) top = f; }
    for (let a = 0; a < na; a++) {
      stroomUit[a] += (tmp[a] / top - stroomUit[a]) * KS;
      aanUit[a] += ((stroomUit[a] > DR ? 1 : 0) - aanUit[a]) * KA;
      if (aanUit[a] > 0.5) lichtUit.push(a);
      if (aanUit[a] > 0.02) streep(G.knoop[nK - 1][a], G.uit, stroomUit[a], aanUit[a], (bedradingUit && bedradingUit[a] < 0) ? -1 : 1);
    } }
}

/* ---- de vonkjes: over een draad waar nu stroom staat, van knoop naar knoop ---- */
function vonk(t) {
  if (RUSTIG || !G.knoop || !stroom.length) return;
  const nK = G.nK;
  for (let v = 0; v < 3; v++) {
    const z = (t | 0) * 7 + v * 131, c = Math.floor(rnd(z) * (nK + 1)) - 1;      // -1 .. nK-1
    let keuze = null, beste = 0;                                                   // alleen over een draad die nu ook echt oplicht
    let tk = 0;
    if (c < 0) { if (lichtIn.length) { const g = lichtIn[Math.floor(rnd(z + 3) * lichtIn.length)]; keuze = [0, g]; beste = stroomIn[g]; } }
    else if (c >= nK - 1) { if (lichtUit.length) { const a = lichtUit[Math.floor(rnd(z + 3) * lichtUit.length)]; keuze = [a, 0]; beste = stroomUit[a]; tk = (bedradingUit && bedradingUit[a] < 0) ? -1 : 1; } }
    else { const kand = lichtTussen[c]; if (kand && kand.length) { const i = kand[Math.floor(rnd(z + 3) * kand.length)], [a, b, , t] = paren[c][i]; keuze = [a, b]; beste = stroom[c][i]; tk = t; } }
    if (keuze) vonken.push({c, a: keuze[0], b: keuze[1], tk, t0: t + v * 70, duur: 520 + 200 * (1 - Math.min(1, beste))});
  }
  if (vonken.length > 90) vonken = vonken.slice(-90);
}

/* ---- bediening: aanwijzen en klikken ---- */
let sleep = null, hover = {station: null, kanaal: null, groep: null};
function schermXY(e) { const r = doek.getBoundingClientRect(); const p = e.touches ? e.touches[0] : e; return {x: (p.clientX - r.left) * DPR, y: (p.clientY - r.top) * DPR}; }
doek.addEventListener("pointermove", e => { muis = schermXY(e); laatstBediend = performance.now(); });
doek.addEventListener("pointerleave", () => { muis = null; hover = {station: null, kanaal: null, groep: null}; });
doek.addEventListener("pointerup", e => {
  const p = schermXY(e); muis = p;
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
  hover = {station: null, kanaal: null, groep: null};
  if (!muis || zoom.t > 0.5 || !G.knoop) return;
  const nK = G.nK, fs = P.fs; let best = (fs * 0.9) ** 2;
  for (let c = 0; c < nK; c++) for (let g = 0; g < KOL[c]; g++) {
    const p = G.knoop[c][g], d = (p[0] - muis.x) ** 2 + (p[1] - muis.y) ** 2;
    if (d < best) { best = d; hover.station = c; hover.groep = g; hover.kanaal = Math.min(spec.breedte - 1, g * Math.max(1, Math.floor(spec.breedte / KOL[c]))); }
  }
  if (hover.station !== null) return;
  if ((G.uit[0] - muis.x) ** 2 + (G.uit[1] - muis.y) ** 2 < (fs * 1.4) ** 2) { hover.station = KOL.length - 1; return; }
  for (let c = 0; c < nK; c++) { const p = G.label[c]; if (Math.abs(p[0] - muis.x) < fs * (G.staand ? 1.6 : 1.1) && Math.abs(p[1] - muis.y) < fs * (G.staand ? 0.7 : 0.9)) { hover.station = c; return; } }
}

/* ---- helpers ---- */
function rondRect(q, x, y, w, h, r) { q.beginPath(); q.moveTo(x + r, y); q.arcTo(x + w, y, x + w, y + h, r); q.arcTo(x + w, y + h, x, y + h, r); q.arcTo(x, y + h, x, y, r); q.arcTo(x, y, x + w, y, r); q.closePath(); }
function warm(v) {                       // gewicht -> kleur (de microscoop): mint plus, koraal min, zoals in het weefsel
  const a = Math.min(1, Math.abs(v));
  return v >= 0 ? `rgba(${TINT.plus},${(0.08 + 0.92 * a).toFixed(3)})` : `rgba(${TINT.min},${(0.08 + 0.92 * a).toFixed(3)})`;
}
let basis = [], devSchaal = [], geleerdTot = 0, basisN = 0;
function leerBasis(rij) {                 // een nieuwe doorgang: haar gewone niveau per groep bijwerken (lopend gemiddelde, ook over gedachten heen)
  const alfa = basisN < 20 ? 0.2 : 0.03;
  for (let k = 0; k < KOL.length; k++) {
    const v = rij[k] || [], nk = KOL[k];
    if (!basis[k] || basis[k].length !== nk) { basis[k] = new Float32Array(nk); devSchaal[k] = 0; }
    const b = basis[k]; let m = 0;
    for (let i = 0; i < nk; i++) { const d = (v[i] || 0) - b[i]; if (d > m) m = d; }
    devSchaal[k] += (m - devSchaal[k]) * alfa;
    for (let i = 0; i < nk; i++) b[i] += ((v[i] || 0) - b[i]) * alfa;
  }
  basisN++;
}
function nieuwVan(j, k, i) {              // een groep in doorgang j: hoeveel hij nú boven zijn gewone niveau uitkomt, 0..1 (de uitvoer: gewoon haar zekerheid)
  const rij = rijen[j]; if (!rij) return 0;
  const x = (rij[k] || [])[i] || 0;
  if (KOL[k] === 1) return Math.min(1, x / kolMax[k]);
  const b = basis[k] ? basis[k][i] : 0, sch = 0.8 * (devSchaal[k] || 0) + 0.000001;
  return Math.min(1, Math.max(0, x - b) / sch);
}
function activiteitVan(j, k, i) {         // een groep in doorgang j: 0..1 ten opzichte van het maximum van die laag in deze gedachte
  const rij = rijen[j]; if (!rij) return 0;
  return Math.min(1, ((rij[k] || [])[i] || 0) / kolMax[k]);
}
function activiteitKanaal(k, c) { return gladKan[k] ? gladKan[k][c] : 0; }
function activiteitGroep(k, g) { return glad[k] ? glad[k][g] : 0; }
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
function tekst(s, x, y, kl, maat, uitl) { ctx.fillStyle = kl; ctx.font = `700 ${P.fs * (maat || 0.62)}px "JetBrains Mono", ui-monospace, monospace`; ctx.textAlign = uitl || "left"; ctx.fillText(s, x, y); }
function knip(s, maxB) { if (ctx.measureText(s).width <= maxB) return s; while (s.length > 1 && ctx.measureText(s + "…").width > maxB) s = s.slice(0, -1); return s + "…"; }

/* ---- de waaier: elk beeld ---- */
function tekenRuimte(t, j, veeg, alpha) {
  if (glad.length !== KOL.length) bouwVorm();
  if (vuil || !G.knoop) projecteer();
  if (vezelBron !== bedrading || vezelMaat !== B + "x" + H + "|" + KOL.join(",")) { bouwVezels(); }
  ctx.globalAlpha = alpha;
  const rij = (j >= 0 && rijen[j]) ? rijen[j] : null, n = KOL.length, nK = G.nK, fs = P.fs;
  if (rijen.length < geleerdTot) geleerdTot = 0;                       // een nieuwe gedachte: de basis blijft, de teller niet
  while (geleerdTot < rijen.length) leerBasis(rijen[geleerdTot++]);
  for (let k = 0; k < n; k++) { const g = glad[k]; if (!g) continue; for (let i = 0; i < g.length; i++) { const doel = rij ? nieuwVan(j, k, i) : 0; g[i] += (doel - g[i]) * 0.12; } }
  if (t - tik > 100) {                   // tien keer per seconde: de kanalen (voor het aanwijzen en de microscoop)
    tik = t;
    for (let k = 1; k <= n - 2; k++) { const d = doelKanalen(j, k), g = gladKan[k]; if (g) for (let c = 0; c < d.length; c++) g[c] += (d[c] - g[c]) * 0.35; }
  }
  // de opbouw: één keer, van links naar rechts (op de telefoon van boven naar onder), daarna staat het
  let front = 1;
  if (!opbouw.klaar) {
    if (!opbouw.t0 && (bedrading || t > 2500)) opbouw.t0 = t;
    if (!opbouw.t0) front = 0;
    else { const p = Math.min(1, (t - opbouw.t0) / 3000); front = p < 0.5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2; if (p >= 1) opbouw.klaar = true; }
  }
  ctx.save();
  if (front < 1) { const tot = G.uA + G.span * (0.02 + 1.0 * front); ctx.beginPath(); if (G.staand) ctx.rect(0, 0, B, tot); else ctx.rect(0, 0, tot, H); ctx.clip(); }
  // de stille laag (eigen canvas eronder): meegroeien met de opbouw, meevervagen met de microscoop
  { const tot = G.uA + G.span * (0.02 + front), clip = front < 1 ? (G.staand ? `inset(0 0 ${(100 * Math.max(0, 1 - tot / H)).toFixed(2)}% 0)` : `inset(0 ${(100 * Math.max(0, 1 - tot / B)).toFixed(2)}% 0 0)`) : "none";
    if (clip !== stilStijl.clip) { stilStijl.clip = clip; stil.style.clipPath = clip; }
    const al = alpha.toFixed(3); if (al !== stilStijl.alpha) { stilStijl.alpha = al; stil.style.opacity = al; } }
  tekenLicht();
  // de knopen: een gloed naar de activiteit van de groep
  const S = G.gloeiS;
  for (let c = 0; c < nK; c++) { const g = glad[c], kol = G.knoop[c]; for (let i = 0; i < kol.length; i++) { const lvl = nivo(g ? g[i] : 0); ctx.drawImage(gloei, lvl * S, 0, S, S, kol[i][0] - S / 2, kol[i][1] - S / 2, S, S); } }
  // de uitvoer: haar zekerheid over het teken van nu
  const zeker = glad[n - 1] ? glad[n - 1][0] : 0;
  { const lvl = nivo(zeker), s2 = S * 1.6; ctx.drawImage(gloei, lvl * S, 0, S, S, G.uit[0] - s2 / 2, G.uit[1] - s2 / 2, s2, s2); }
  // het punt: haar vraag komt hier binnen
  { const s3 = S * 2.6; ctx.globalAlpha = alpha * 0.9; ctx.drawImage(gloei, 5 * S, 0, S, S, G.punt[0] - s3 / 2, G.punt[1] - s3 / 2, s3, s3); ctx.globalAlpha = alpha; ctx.fillStyle = "#FFFFFF"; ctx.beginPath(); ctx.arc(G.punt[0], G.punt[1], DPR * 2.4, 0, 7); ctx.fill(); }
  // de vonkjes
  const nu = performance.now();
  vonken = vonken.filter(v => nu - v.t0 < v.duur);
  for (const v of vonken) {
    const u = (nu - v.t0) / v.duur; if (u < 0) continue;
    const [a, b] = eind(v.c, v.a, v.b), [x, y] = opPad(a, b, u), f = Math.sin(u * Math.PI);
    ctx.fillStyle = `rgba(${tekenKleur(v.tk)},${(0.9 * f).toFixed(2)})`; ctx.beginPath(); ctx.arc(x, y, DPR * 2.0, 0, 7); ctx.fill();
    ctx.fillStyle = `rgba(255,255,255,${(0.8 * f).toFixed(2)})`; ctx.beginPath(); ctx.arc(x, y, DPR * 0.9, 0, 7); ctx.fill();
  }
  // de namen: de vraag bij het punt, de lagen onder de kolommen, de uitvoer
  ctx.textBaseline = "middle";
  const vraag = stand ? (stand.opgave || "").replace(/\n/g, " ; ") : "";
  if (G.staand) {
    tekst("VRAAG", G.punt[0] + fs * 2.4, G.punt[1] - fs * 0.6, `rgba(${TINT.draad},0.85)`, 0.6);
    ctx.font = `500 ${fs * 0.62}px "JetBrains Mono", ui-monospace, monospace`; ctx.fillStyle = `rgba(${TINT.draad},0.6)`; ctx.textAlign = "left";
    ctx.fillText(knip(vraag, G.dwars * 0.5 - fs * 3), G.punt[0] + fs * 2.4, G.punt[1] + fs * 0.6);
  } else {
    tekst("VRAAG", G.punt[0], G.punt[1] - fs * 1.6, `rgba(${TINT.draad},0.85)`, 0.6, "center");
    ctx.font = `500 ${fs * 0.62}px "JetBrains Mono", ui-monospace, monospace`; ctx.fillStyle = `rgba(${TINT.draad},0.6)`; ctx.textAlign = "left";
    ctx.fillText(knip(vraag, G.span * 0.5), P.vrijX + fs * 0.4, P.vrijY + fs * 0.8);
  }
  for (let c = 0; c < nK; c++) {
    const licht = hover.station === c || (zoom.laag === c && zoom.doel), naam = c === 0 ? "IN" : "L" + c;
    if (G.staand && !licht && c % 2 === 0 && c > 0) continue;          // op de telefoon om en om, anders staan ze op elkaar
    tekst(naam, G.label[c][0], G.label[c][1], licht ? "rgba(255,255,255,0.95)" : `rgba(${TINT.draad},0.55)`, 0.56, "center");
    if (licht) { const kol = G.knoop[c], a = kol[0], b = kol[kol.length - 1]; ctx.strokeStyle = "rgba(255,255,255,0.5)"; ctx.lineWidth = DPR; ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); }
  }
  if (hover.station !== null && hover.groep !== null && G.knoop[hover.station]) { const p = G.knoop[hover.station][hover.groep]; ctx.strokeStyle = "rgba(255,255,255,0.95)"; ctx.lineWidth = DPR; ctx.beginPath(); ctx.arc(p[0], p[1], fs * 0.5, 0, 7); ctx.stroke(); }
  const uitLicht = hover.station === n - 1 || (zoom.laag === n - 1 && zoom.doel);
  if (G.staand) { tekst(`UITVOER · ZEKERHEID ${Math.round(100 * zeker)}%`, G.uit[0] - fs * 1.4, G.uit[1], uitLicht ? "rgba(255,255,255,0.95)" : `rgba(${TINT.draad},0.85)`, 0.6, "right"); }
  else { tekst("UITVOER", G.uit[0], G.uit[1] - fs * 1.7, uitLicht ? "rgba(255,255,255,0.95)" : `rgba(${TINT.draad},0.85)`, 0.6, "center"); tekst(`ZEKERHEID ${Math.round(100 * zeker)}%`, G.uit[0], G.uit[1] + fs * 1.7, `rgba(${TINT.draad},0.7)`, 0.56, "center"); }
  tekst(`${n - 2} LAGEN × ${KOL[1]} GROEPEN · ELKE DRAAD EEN GEWICHT · GROEN = PLUS · ROOD = MIN · LICHT = WAT NU BOVEN HAAR GEWONE NIVEAU UITKOMT`, G.staand ? P.vrijX + fs * 0.4 : P.vrijX + P.vrijB - fs * 0.4, G.staand ? P.vrijY + P.vrijH - fs * 0.6 : P.vrijY + fs * 2.4, `rgba(${TINT.draad},0.5)`, 0.5, G.staand ? "left" : "right");   // tweede regel, onder de vraag
  ctx.restore(); ctx.textBaseline = "alphabetic"; ctx.globalAlpha = 1;
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
let laatstMeld = 0, beelden = 0, laatsteVonk = 0;
// de kijker bewaart de laatste 48 doorgangen; bij een langer antwoord begint
// de eerste dus niet bij het lezen van de vraag maar bij een teken verderop
const verschuiving = () => Math.max(0, antwoordDoel.length + 1 - rijen.length);
function teken(t) {
  if (FOTO && ++beelden > 40 && beelden % 6) { requestAnimationFrame(teken); return; }   // proefopname: na 40 beelden nog maar één op de zes (anders loopt de opname vast)
  ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
  ctx.clearRect(0, 0, B, H);
  if (!rijen.length && wachtrij.length) nieuweGedachte(t);
  const n = rijen.length;
  let j = -1, veeg = 0;
  if (n) {
    if (LIVE && vast === null) { j = herhaal ? Math.max(0, Math.min(n - 1, herhaalJ)) : n - 1; veeg = 1; }
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
  if (vuil) projecteer();
  // de vonkjes (25 aug, Cley: "er moet elke keer een puls doorheen gaan, het mag niet stoppen"):
  // elke 120 ms over een draad waar nu stroom staat, ook tussen twee gedachten -- nooit over het hele scherm
  if (zoom.t < 0.5 && t - laatsteVonk > 120) { laatsteVonk = t; vonk(t); }
  zoekHover();
  zoom.t += ((zoom.doel || 0) - zoom.t) * 0.12;
  if (Math.abs(zoom.t - (zoom.doel || 0)) < 0.002) zoom.t = zoom.doel || 0;
  if (zoom.t < 0.999) tekenRuimte(t, j, veeg, 1 - zoom.t);
  if (zoom.t > 0.001 && zoom.laag !== null) tekenLaag(t, j, zoom.t);
  doek.style.cursor = (hover.station !== null || zoom.t > 0.5) ? "pointer" : "default";
  if (t - laatstMeld > 100) { laatstMeld = t; if (typeof toonOnderschrift === "function") toonOnderschrift(j, n); }
  if (!LIVE && n && vast === null && klaarSinds && t - klaarSinds > 7000) { if (wachtrij.length) nieuweGedachte(t); else { speelStart = t; klaarSinds = 0; } }
  requestAnimationFrame(teken);
}
requestAnimationFrame(teken);
