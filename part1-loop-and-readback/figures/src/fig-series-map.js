// Series map for the agent design series: the model in the middle, the harness around it holding six
// runtime jobs, and two team jobs outside the harness. Each job carries its part number. One job is
// drawn in gold: the part the reader is in.
// Built to be read at 400 px wide (a 1200-wide canvas shows at 1/3 there), so no text is under 30 px.
// Run: node fig-series-map.js [part]   (default 1)  -> ../series-map-part<part>.png  (OUT=<dir> to write elsewhere)
// The geometry trace at the bottom fails the run on any overlap, escape or banned character.
const A = require('./arch');
const PART = Number(process.argv[2] || process.env.PART || 1);
const WD = 1200;
const f = A.fig(WD);
const { P } = f;
const MONO = 'Menlo, monospace';

const JOBS = [
  { n: 1, name: 'Loop and read-back' },
  { n: 2, name: 'Tools' },
  { n: 3, name: 'Context and memory' },
  { n: 4, name: 'Sub-agents and handoffs' },
  { n: 5, name: 'Recovery' },
  { n: 6, name: 'Authority' },
  { n: 7, name: 'Evidence before release' },
  { n: 8, name: 'Ownership after launch' },
];
if (!JOBS.some(j => j.n === PART)) throw new Error(`part must be 1 to 8, got ${process.argv[2]}`);
const HL = JOBS.find(j => j.n === PART);

// ---- geometry trace ----
const boxes = []; const conts = {}; const notes = [];
function T(x, y, s, o = {}, inside = null) {
  if (/[–—;]/.test(s)) notes.push(`dash or semicolon in figure text: "${s}"`);
  const size = o.size || 30;
  if (size < 30) notes.push(`text below 30 px: "${s}"`);
  const w = f.text(x, y, s, { ...o, size });
  const anchor = o.anchor || 'start';
  const x0 = anchor === 'middle' ? x - w / 2 : anchor === 'end' ? x - w : x;
  boxes.push({ s, x0, y0: y - size * 0.76, x1: x0 + w, y1: y + size * 0.24, in: inside });
  return w;
}
const cont = (name, x0, y0, x1, y1) => (conts[name] = { x0, y0, x1, y1 });

// ---- header ----
let y = 64;
const eyebrow = `SERIES MAP, PART ${PART} OF 8`;
T(60, y, eyebrow, { size: 30, family: MONO, fill: P.GOLD_TEXT, spacing: 3 });
f.raw(`<line x1="60" y1="${y + 22}" x2="${WD - 60}" y2="${y + 22}" stroke="${P.GOLD}" stroke-width="2"/>`);
y += 92;
const HEAD = 'Eight jobs around the model, one for each part';
const heads = f.wrap(HEAD, WD - 120, 48, true);
heads.forEach((s, i) => T(60, y + i * 58, s, { size: 48, weight: 700 }));
y += (heads.length - 1) * 58 + 30;

// ---- harness: a filled ellipse, the model in the middle ----
const CW = 320, CH = 112, TS = 31, LH = 37, BR = 25;
const a = 180, b = 222, c = 372;              // chip centre offsets from the ellipse centre
const RX = 572, RY = 408, D = 16;          // D: the model and chips sit this far below the ellipse centre
const ECX = WD / 2, ECY = y + 24 + RY, MCY = ECY + D;
f.raw(`<ellipse cx="${ECX}" cy="${ECY}" rx="${RX}" ry="${RY}" fill="${P.COOL_FILL}" stroke="${P.COOL}" stroke-width="2.5"/>`);
const MR = 140;
f.raw(`<circle cx="${ECX}" cy="${MCY}" r="${MR}" fill="#FFFFFF" stroke="${P.INK3}" stroke-width="2"/>`);
cont('model', ECX - MR * 0.7, MCY - MR * 0.7, ECX + MR * 0.7, MCY + MR * 0.7);
T(ECX, MCY + 0.36 * 44, 'Model', { size: 44, weight: 700, anchor: 'middle' }, 'model');

// ring label at the top of the ellipse
const LY = ECY - RY + 62;
cont('harness-label', ECX - 250, LY - 40, ECX + 250, LY + 60);
T(ECX, LY, 'Harness', { size: 36, weight: 700, fill: P.COOL, anchor: 'middle' }, 'harness-label');
T(ECX, LY + 40, 'code around the model', { size: 30, fill: P.INK2, anchor: 'middle' }, 'harness-label');

// a chip: number badge and name, centred as one group
const chips = [];
function chip(cx, cy, job, team) {
  const hl = job.n === PART;
  const x = cx - CW / 2, yy = cy - CH / 2;
  const fill = hl ? P.GOLD_FILL : '#FFFFFF';
  const stroke = hl ? P.GOLD : team ? P.INK3 : P.COOL;
  f.raw(`<rect x="${x}" y="${yy}" width="${CW}" height="${CH}" rx="12" fill="${fill}" stroke="${stroke}" stroke-width="${hl ? 4.5 : 2}"/>`);
  const name = `chip${job.n}`;
  cont(name, x, yy, x + CW, yy + CH);
  chips.push({ name, x0: x, y0: yy, x1: x + CW, y1: yy + CH, team });
  const pad = 16, gap = 14;
  const lines = f.wrap(job.name, CW - 2 * pad - 2 * BR - gap, TS, true);
  if (lines.length > 2) notes.push(`chip name needs ${lines.length} lines: "${job.name}"`);
  const tw = Math.max(...lines.map(s => f.width(s, TS, true)));
  const gx = cx - (2 * BR + gap + tw) / 2;
  const badge = hl ? P.GOLD : team ? P.INK3 : P.COOL;
  f.raw(`<circle cx="${gx + BR}" cy="${cy}" r="${BR}" fill="${badge}"/>`);
  T(gx + BR, cy + 0.36 * 30, String(job.n), { size: 30, weight: 700, fill: hl ? P.INK : '#FFFFFF', anchor: 'middle' }, name);
  lines.forEach((s, i) => T(gx + 2 * BR + gap, cy - ((lines.length - 1) * LH) / 2 + 0.36 * TS + i * LH, s,
    { size: TS, weight: 700, fill: P.INK }, name));
}
// clockwise from the top left
const POS = [[-a, -b], [a, -b], [c, 0], [a, b], [-a, b], [-c, 0]];
POS.forEach(([dx, dy], i) => chip(ECX + dx, MCY + dy, JOBS[i], false));

// ---- team jobs, outside the harness ----
const TY = ECY + RY + 40;
const TH = 236;
f.group(60, TY, WD - 120, TH, '', { stroke: P.INK3, dashed: true });
cont('team', 60, TY, WD - 60, TY + TH);
T(WD / 2, TY + 50, 'Team jobs, outside the harness', { size: 32, weight: 700, fill: P.INK2, anchor: 'middle' }, 'team');
const TCY = TY + 80 + CH / 2 + 4;
// same columns as chips 1/5 and 2/4 above, so the two rows line up
chip(ECX - a, TCY, JOBS[6], true);
chip(ECX + a, TCY, JOBS[7], true);

// ---- checks ----
function check() {
  const out = [...notes];
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const p = boxes[i], q = boxes[j];
    if (p.x0 < q.x1 && q.x0 < p.x1 && p.y0 < q.y1 && q.y0 < p.y1) out.push(`text overlap: "${p.s}" / "${q.s}"`);
  }
  for (const t of boxes) if (t.in) {
    const k = conts[t.in], pad = t.in.startsWith('chip') ? 12 : 4;
    if (t.x0 < k.x0 + pad || t.x1 > k.x1 - pad || t.y0 < k.y0 + 8 || t.y1 > k.y1 - 8)
      out.push(`text escapes ${t.in}: "${t.s}"`);
  }
  // text that sits in no container must not touch any chip
  for (const t of boxes) if (!t.in) for (const k of chips)
    if (t.x0 < k.x1 && k.x0 < t.x1 && t.y0 < k.y1 && k.y0 < t.y1) out.push(`text over ${k.name}: "${t.s}"`);
  // chips: no overlap, at least 24 px apart
  for (let i = 0; i < chips.length; i++) for (let j = i + 1; j < chips.length; j++) {
    const p = chips[i], q = chips[j], g = 24;
    if (p.x0 - g < q.x1 && q.x0 - g < p.x1 && p.y0 - g < q.y1 && q.y0 - g < p.y1) out.push(`chips too close: ${p.name} / ${q.name}`);
  }
  // harness chips sit inside the ellipse with room, clear of the model circle and the label
  // inside the ellipse shrunk by m px on both axes (<= 1 means at least m px from the edge, roughly)
  const inE = (x, y, m = 24) => ((x - ECX) / (RX - m)) ** 2 + ((y - ECY) / (RY - m)) ** 2;
  for (const k of chips.filter(k => !k.team)) {
    for (const [x, yy] of [[k.x0, k.y0], [k.x1, k.y0], [k.x0, k.y1], [k.x1, k.y1]])
      if (inE(x, yy) > 1) out.push(`${k.name} corner too close to the ellipse edge (${inE(x, yy).toFixed(2)})`);
    const nx = Math.max(k.x0, Math.min(ECX, k.x1)), ny = Math.max(k.y0, Math.min(MCY, k.y1));
    if (Math.hypot(nx - ECX, ny - MCY) < MR + 24) out.push(`${k.name} too close to the model circle`);
    const L = conts['harness-label'];
    if (k.y0 < L.y1 && k.x0 < L.x1 && L.x0 < k.x1) out.push(`${k.name} runs into the harness label`);
  }
  if (ECX - RX < 20 || ECX + RX > WD - 20) out.push('ellipse runs off the canvas');
  const L = conts['harness-label'];
  for (const t of boxes.filter(t => t.in === 'harness-label'))
    for (const [x, yy] of [[t.x0, t.y0], [t.x1, t.y0]]) if (inE(x, yy) > 1) out.push(`label too close to the ellipse edge: "${t.s}"`);
  if (L.y0 < ECY - RY) out.push('label above the ellipse');
  const lowest = Math.max(...chips.filter(k => !k.team).map(k => k.y1));
  console.log(`space above the top chips: ${(Math.min(...chips.filter(k => !k.team).map(k => k.y0)) - (ECY - RY)).toFixed(0)} px, below the bottom chips: ${(ECY + RY - lowest).toFixed(0)} px`);
  return out;
}

(async () => {
  const problems = check();
  // OUT=<dir> writes a test render somewhere else (the default is the figures folder)
  const warn = await f.render(`series-map-part${PART}`, [], process.env.OUT || undefined, { gap: 0 });
  const all = [...problems, ...warn];
  if (all.length) { console.log('GEOMETRY:\n  ' + all.join('\n  ')); process.exitCode = 1; }
  else console.log('geometry clean:', boxes.length, 'texts,', chips.length, 'chips');
})();
