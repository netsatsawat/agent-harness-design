// The harness design review on one page: one row per part of the series map, with the question the part answers,
// one pattern, one anti-pattern and the part that goes deep. Row 1 is drawn in gold: the part the reader is in.
// Pattern and anti-pattern wording is taken word for word from the numbered list under '## A harness design review'
// in part1-loop-and-readback/README.md. To check that the figure still matches a text, set
// WORDING=<file.md>: the build reads the numbered list in that file's '## A harness design review' section and
// fails if any cell is no longer in it, so the figure and the text cannot drift apart. Without WORDING the check
// is skipped. The questions are new to the figure (the text has no question per part), written from each row's pattern.
// No measured numbers appear here. Row numbers are part numbers, as on the series map.
// 1200 wide so it still reads at 400 px (no text under 28 px, cells at 30). Run: node fig-design-review.js  (OUT=<dir> elsewhere)
const fs = require('fs');
const path = require('path');
const A = require('./arch');
const WD = 1200;
const f = A.fig(WD);
const { P } = f;
const MONO = 'Menlo, monospace';
const PART = 1;

const ROWS = [
  { n: 1, job: 'Loop and read-back', q: 'What does the model read back, and when does the run stop?',
    p: 'Code writes what the model reads and decides when to stop',
    a: 'Run on framework defaults nobody read' },
  { n: 2, job: 'Tools', q: 'Which tools does the model get?',
    p: 'Load the tools every task needs, and test the search for the rest',
    a: 'Load every tool, or trust an untested tool search' },
  { n: 3, job: 'Context and memory', q: 'What must the model always remember?',
    p: 'Keep standing rules in a file added to every call',
    a: 'Trust automatic compaction, which may drop early instructions' },
  { n: 4, job: 'Sub-agents and handoffs', q: 'What must a sub-agent hand back?',
    p: "Define what a sub-agent's answer must carry back",
    a: 'Accept a free-form summary that drops a rule' },
  { n: 5, job: 'Recovery', q: 'Is it safe to retry a write?',
    p: 'Put an idempotency key on every tool that changes data',
    a: 'Retry or resume a write without one' },
  { n: 6, job: 'Authority', q: 'Where is each rule enforced?',
    p: 'Enforce rules in the tool or an approval step',
    a: 'A rule only in the prompt, with approval off' },
  { n: 7, job: 'Evidence before release', team: true, q: 'What proves a change works?',
    p: "Run each change many times and grade the outcome against the user's request",
    a: 'Ship on one good run' },
  { n: 8, job: 'Ownership after launch', team: true, q: 'Who looks after the agent once it ships?',
    p: 'Name who reads traces and who removes parts a newer model no longer needs',
    a: 'Keep every workaround' },
];

// ---- geometry trace ----
const boxes = []; const conts = {}; const notes = [];
function T(x, y, s, o = {}, inside = null) {
  if (/[–—;]/.test(s)) notes.push(`dash or semicolon in figure text: "${s}"`);
  if (/\bI ran\b/i.test(s)) notes.push(`"I ran" in figure text: "${s}"`);
  const size = o.size || 28;
  if (size < 28) notes.push(`text below 28 px: "${s}"`);
  const w = f.text(x, y, s, { ...o, size });
  const anchor = o.anchor || 'start';
  const x0 = anchor === 'middle' ? x - w / 2 : anchor === 'end' ? x - w : x;
  boxes.push({ s, x0, y0: y - size * 0.76, x1: x0 + w, y1: y + size * 0.24, in: inside });
  return w;
}
const cont = (name, x0, y0, x1, y1) => (conts[name] = { x0, y0, x1, y1 });

// ---- the wording check (opt-in): every pattern and anti-pattern must be in the text's design review list ----
const wordingFile = process.env.WORDING ? path.resolve(process.env.WORDING) : null;
if (!wordingFile) console.log('wording check skipped (set WORDING=<file.md> to run it)');
else if (!fs.existsSync(wordingFile)) notes.push(`WORDING file not found: ${wordingFile}`);
else {
  const md = fs.readFileSync(wordingFile, 'utf8');
  const sec = md.split(/^## /m).find(s => s.startsWith('A harness design review')) || '';
  if (!sec) notes.push(`no design review section in ${path.basename(wordingFile)}`);
  for (const r of ROWS) {
    const line = (sec.split('\n').find(l => l.startsWith(`${r.n}. `)) || '')
      .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/\s+/g, ' ');
    const low = line.toLowerCase();
    if (!line.includes(`**${r.job}**`)) notes.push(`row ${r.n}: job name "${r.job}" not in the WORDING list`);
    const part = r.n === PART ? '(this part)' : `(Part ${r.n}${r.team ? ', team work' : ''})`;
    if (!line.includes(part)) notes.push(`row ${r.n}: "${part}" not in the WORDING list`);
    if (!low.includes(`pattern: ${r.p.toLowerCase()}`)) notes.push(`row ${r.n}: pattern differs from WORDING: "${r.p}"`);
    if (!low.includes(`anti-pattern: ${r.a.toLowerCase()}`)) notes.push(`row ${r.n}: anti-pattern differs from WORDING: "${r.a}"`);
  }
  console.log('wording checked against', path.basename(wordingFile));
}

// ---- header ----
let y = 64;
T(60, y, 'HARNESS DESIGN REVIEW', { size: 28, family: MONO, fill: P.GOLD_TEXT, spacing: 3 });
f.raw(`<line x1="60" y1="${y + 22}" x2="${WD - 60}" y2="${y + 22}" stroke="${P.GOLD}" stroke-width="2"/>`);
y += 92;
// 'This design review works with any model or framework' was 1210 px at 46 bold, past the 1080 line, so it got shorter.
// The heading names frameworks too, because the patterns hold beyond the OpenAI SDK (see framework-defaults/).
const HEAD = 'A design review for any model or framework';
if (f.width(HEAD, 46, true) > WD - 120) notes.push(`heading too wide: ${Math.round(f.width(HEAD, 46, true))}`);
T(60, y, HEAD, { size: 46, weight: 700 });
y += 54;
// balanced by hand: 520 and 549 px, and 'one anti-pattern' stays on one line
const DEK = ['Each part gets one pattern to build and', 'one anti-pattern to look for in your traces.'];
DEK.forEach((s, i) => T(60, y + i * 38, s, { size: 30, fill: P.INK2 }));
y += (DEK.length - 1) * 38 + 66;

// ---- columns ----
// cards run 20 px outside the text margin, so cell text lines up with the header at x = 60
const CX0 = 40, CX1 = WD - 40, PAD = 20;          // card edges and inner padding
const GAP = 40;                                    // gap between cells, a thin rule in the middle
const CW = [290, 380, 330];                        // question, pattern, anti-pattern (fewest lines, no one-word last line)
const COLX = [CX0 + PAD]; for (let i = 1; i < 3; i++) COLX.push(COLX[i - 1] + CW[i - 1] + GAP);
if (COLX[2] + CW[2] !== CX1 - PAD) notes.push(`columns do not fill the card: ${COLX[2] + CW[2]} vs ${CX1 - PAD}`);
const HEADS = [
  { s: 'Question it answers', fill: P.INK2 },
  { s: 'Pattern', fill: P.GREEN },
  { s: 'Anti-pattern', fill: P.WARN_TEXT },
];
HEADS.forEach((h, i) => T(COLX[i], y, h.s, { size: 30, weight: 700, fill: h.fill }));
T(CX1 - PAD, y, 'Part', { size: 30, weight: 700, fill: P.INK2, anchor: 'end' });
y += 26;

// ---- rows ----
const SZ = 30, LH = 38, BR = 22, NAME = 32;
// balanced wrap: the fewest lines the column allows, then the narrowest width that keeps that count
function bwrap(s, W, size) {
  const n = f.wrap(s, W, size).length; let lo = 40, hi = W;
  while (hi - lo > 1) { const m = (lo + hi) / 2; if (f.wrap(s, m, size).length > n) lo = m; else hi = m; }
  return f.wrap(s, hi, size);
}
const lay = r => [r.q, r.p, r.a].map((s, i) => {
  const ls = bwrap(s, CW[i], SZ);
  if (ls.length > 1 && !/\s/.test(ls[ls.length - 1].trim())) notes.push(`row ${r.n}: one-word last line "${ls[ls.length - 1]}"`);
  if (ls.length > 4) notes.push(`row ${r.n}: a cell needs ${ls.length} lines: "${s}"`);
  return ls;
});
const RGAP = 14;
const cards = [];
function row(r, top) {
  const hl = r.n === PART;
  const cells = lay(r);
  const n = Math.max(...cells.map(c => c.length));
  const bandTop = top + 18, bcy = bandTop + BR;            // title band: badge and job name
  const hair = bandTop + 2 * BR + 12;                       // hairline under the band
  const cellTop = hair + 12;                                // cells start under the hairline
  const first = cellTop + SZ * 0.76;
  const h = (first + (n - 1) * LH + SZ * 0.24 + 22) - top;
  const fill = hl ? P.GOLD_FILL : '#FFFFFF';
  const stroke = hl ? P.GOLD : r.team ? P.INK3 : P.RULE;
  f.raw(`<rect x="${CX0}" y="${top}" width="${CX1 - CX0}" height="${h}" rx="12" fill="${fill}" stroke="${stroke}" stroke-width="${hl ? 4 : 1.6}"/>`);
  const name = `row${r.n}`;
  cont(name, CX0, top, CX1, top + h);
  cards.push({ name, x0: CX0, y0: top, x1: CX1, y1: top + h });
  // badge and job name
  const badge = hl ? P.GOLD : r.team ? P.INK3 : P.COOL;
  const bx = CX0 + PAD + BR;
  f.raw(`<circle cx="${bx}" cy="${bcy}" r="${BR}" fill="${badge}"/>`);
  T(bx, bcy + 0.36 * SZ, String(r.n), { size: SZ, weight: 700, fill: hl ? P.INK : '#FFFFFF', anchor: 'middle' }, name);
  T(bx + BR + 14, bcy + 0.36 * NAME, r.job, { size: NAME, weight: 700 }, name);
  // part label, right aligned on the band
  T(CX1 - PAD, bcy + 0.36 * SZ, hl ? 'This part' : `Part ${r.n}`,
    { size: SZ, weight: hl ? 700 : 400, fill: hl ? P.GOLD_TEXT : P.INK3, anchor: 'end' }, name);
  // a hairline under the band, and thin rules between the cells
  const rule = hl ? P.GOLD : P.RULE;
  f.raw(`<line x1="${CX0 + PAD}" y1="${hair}" x2="${CX1 - PAD}" y2="${hair}" stroke="${rule}" stroke-width="1"/>`);
  // the rule left of each pattern is green and left of each anti-pattern red, the colours of the column heads
  for (let i = 1; i < 3; i++) {
    const vx = COLX[i] - GAP / 2;
    f.raw(`<line x1="${vx}" y1="${cellTop + 2}" x2="${vx}" y2="${top + h - 16}" stroke="${i === 1 ? P.GREEN : P.WARN}" stroke-width="3" stroke-linecap="round"/>`);
    cont(`${name}-div${i}`, vx, cellTop, vx, top + h - 16);
  }
  cells.forEach((ls, i) => {
    cont(`${name}-c${i}`, COLX[i], cellTop - 6, COLX[i] + CW[i], top + h);
    ls.forEach((s, k) => T(COLX[i], first + k * LH, s, { size: SZ, fill: P.INK }, `${name}-c${i}`));
  });
  return top + h;
}

for (const r of ROWS.filter(r => !r.team)) y = row(r, y + (r.n > 1 ? RGAP : 0)) ;

// team work: a dashed frame a little outside the cards, as on the series map
y += 34;
const GX0 = CX0 - 14, GX1 = CX1 + 14, gTop = y;
y += 50;
T(WD / 2, y, 'Team work, outside the harness', { size: 30, weight: 700, fill: P.INK2, anchor: 'middle' }, 'team');
y += 30;
ROWS.filter(r => r.team).forEach((r, i) => { y = row(r, y + (i ? RGAP : 0)); });
y += 24;
// f.group, not f.raw: group() tracks the frame's bottom, so the canvas leaves a margin under it
f.group(GX0, gTop, GX1 - GX0, y - gTop, '', { stroke: P.INK3, dashed: true });
cont('team', GX0, gTop, GX1, y);

// no footer: the figure is the README's own design review, so a source line adds nothing

// ---- checks ----
function check() {
  const out = [...notes];
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const p = boxes[i], q = boxes[j];
    if (p.x0 < q.x1 && q.x0 < p.x1 && p.y0 < q.y1 && q.y0 < p.y1) out.push(`text overlap: "${p.s}" / "${q.s}"`);
  }
  for (const t of boxes) if (t.in) {
    const k = conts[t.in], pad = t.in.startsWith('row') && !t.in.includes('-c') ? 12 : 0;
    if (t.x0 < k.x0 + pad || t.x1 > k.x1 - pad || t.y0 < k.y0 + 6 || t.y1 > k.y1 - 6)
      out.push(`text escapes ${t.in}: "${t.s}"`);
  }
  // text must keep 8 px from the cell rules
  for (const t of boxes) for (const [nm, k] of Object.entries(conts)) if (nm.includes('-div'))
    if (t.x0 - 8 < k.x0 && k.x0 < t.x1 + 8 && t.y0 < k.y1 && k.y0 < t.y1) out.push(`text touches a cell rule: "${t.s}"`);
  // text outside the cards must not touch a card
  for (const t of boxes) if (!t.in || t.in === 'team') for (const k of cards)
    if (t.x0 < k.x1 && k.x0 < t.x1 && t.y0 - 8 < k.y1 && k.y0 < t.y1 + 8) out.push(`text over ${k.name}: "${t.s}"`);
  // the job name must leave room for the part label on the same band
  for (const r of ROWS) {
    const nm = boxes.find(b => b.s === r.job), pt = boxes.find(b => b.in === `row${r.n}` && /^(Part \d|This part)$/.test(b.s));
    if (nm && pt && pt.x0 - nm.x1 < 40) out.push(`row ${r.n}: job name runs close to the part label`);
  }
  return out;
}

(async () => {
  const problems = check();
  const warn = await f.render('design-review', [], process.env.OUT || undefined, { gap: 0 });
  const all = [...problems, ...warn];
  if (all.length) { console.log('GEOMETRY:\n  ' + all.join('\n  ')); process.exitCode = 1; }
  else console.log('geometry clean:', boxes.length, 'texts,', cards.length, 'rows');
})();
