// Hero for Part 1: one failed create_ticket call, then what the model reads back under three harness choices.
// Every string and number here was read from the experiment, not typed from memory:
//   user request    ../../experiment/harness_defaults.py, TASKS['priority'].prompt
//   the call        ../../experiment/sweep/runs.jsonl, gpt-6-astra priority runs: first call {"title": "CSV export on reports page times
//                   out for large date ranges", "priority": "high"} (that exact title in 58 of its 60 priority runs)
//   the 422 body    ../../experiment/servers.py ticket_server, as logged in runs.jsonl server_error (excerpt: loc, msg, input)
//   fixed line      openai-agents 0.24.0 agents/tool.py default_tool_error_function (../../experiment/sdk_defaults.txt)
//   old line        the 0.22.3 default, the exact string runs.jsonl logs as model_read in the old_default arm
//   approved note   harness_defaults.py APPROVED_NOTES['priority'], as logged in the note arm
//   outcomes        ../../experiment/sweep/results.csv rows priority x {default, old_default, note}:
//                   gpt-6-astra 0, 20, 20 of 20. qwen3.5:2b 0, 1, 20 of 20 (old line: wrong_value 19, P0:19).
//                   From runs.jsonl: astra sent "high" on every fixed-line call and gave up in all 20. Every old-line and
//                   note run of both models made exactly two calls, the second one P1 (P0 in 19 qwen 2b old-line runs).
//   versions        0.23.1 first shipped the fixed line on PyPI, 0.22.3 is the last with the error text (sdk_defaults.txt, section 3)
// The service is made up for the test. The README caption says so, not the figure.
// Columns are sized by their content (the fixed line is short, the old line is long), and each top box shares its
// column's x and width, so the error box sits right above the note card and every arrow is straight.
// Layout is flow: every block anchors to the computed bottom of the one above. The checker at the end fails the build on
// text overlap, text outside its box, text on an arrow or box it does not belong to, arrows through boxes, small type,
// dashes or semicolons. Menlo advance is 0.602 em and Helvetica comes from helv_widths.json (both probed against real ink).
// Run: node fig-hero-what-the-model-read.js   (OUT=dir writes the PNG elsewhere, DUMP=dir also writes the SVG)
const A = require('./arch');
const WD = 1400;
const f = A.fig(WD);
const { P } = f;
const MONO = 'Menlo, monospace';
const M = 60, GAP = 50, PAD = 18;
const CODE = 21, CODE_LH = 28, CHAR = CODE * 0.602;
const HL = '#F5E2B0', HL_WARN = '#F6D5CC';               // marker tints behind highlighted code
const NB = ' ';                                      // keeps a code and its meaning on one line

// column widths: col 3 must hold the longest error line, col 1 is narrow for the short fixed line, col 2 takes the rest
const LONGEST_ERR = '"loc": ["body", "priority"],';
const COLW = [330, 0, Math.ceil(LONGEST_ERR.length * CHAR + 2 * PAD + 4)];
COLW[1] = WD - 2 * M - 2 * GAP - COLW[0] - COLW[2];
const COLX = [M, M + COLW[0] + GAP, M + COLW[0] + COLW[1] + 2 * GAP];
const C = COLX.map((x, i) => x + COLW[i] / 2);

// ---- geometry trace ----
const texts = [], rects = [], segs = [], notes = [];
function T(x, y, s, o = {}, host = null) {
  if (/[–—;]/.test(s)) notes.push(`dash or semicolon in figure text: "${s}"`);
  const size = o.size || 26, min = o.family === MONO ? 21 : 24;
  if (size < min) notes.push(`text below ${min} px: "${s}"`);
  const w = f.text(x, y, s, { ...o, size });
  const anchor = o.anchor || 'start';
  const x0 = anchor === 'middle' ? x - w / 2 : anchor === 'end' ? x - w : x;
  texts.push({ s, x0, y0: y - size * 0.76, x1: x0 + w, y1: y + size * 0.24, host, base: y });
  return w;
}
const rect = (name, x, y, w, h) => { const r = { name, x0: x, y0: y, x1: x + w, y1: y + h }; rects.push(r); return r; };
function para(x, y, s, maxW, size, lh, o = {}, host = null) {
  const ls = f.wrap(s, maxW, size, o.weight >= 600);
  if (ls.length > 1 && !/\s/.test(ls[ls.length - 1].trim())) notes.push(`one-word last line: "${ls[ls.length - 1]}"`);
  ls.forEach((t, i) => T(x, y + i * lh, t, { ...o, size }, host));
  return y + (ls.length - 1) * lh;
}
function arrow(pts, from, to) {
  f.arrow(pts, { color: P.INK3, lw: 2.2 });
  for (let i = 0; i < pts.length - 1; i++) segs.push({ a: pts[i], b: pts[i + 1], from, to });
}

// ---- monospace text with highlights ----
// Markup: ⁅...⁆ marks a gold highlight, ⦃...⦄ marks the wrong value, '\n' forces a break, NB never breaks.
// Wraps at spaces by character count (Menlo is fixed width), draws the marker under each run.
function monoLines(markup, maxW) {
  const maxC = Math.floor(maxW / CHAR);
  const chars = []; let st = 0;
  for (const c of markup) {
    if (c === '⁅') st = 1; else if (c === '⦃') st = 2; else if (c === '⁆' || c === '⦄') st = 0;
    else chars.push({ c, st });
  }
  const lines = []; let cur = [], word = [];
  const flush = () => {
    if (!word.length) return;
    if (cur.length && cur.length + 1 + word.length > maxC) { lines.push(cur); cur = []; }
    if (cur.length) cur.push({ c: ' ', st: cur[cur.length - 1].st && word[0].st ? word[0].st : 0 });
    cur.push(...word); word = [];
  };
  for (const ch of chars) {
    if (ch.c === '\n') { flush(); lines.push(cur); cur = []; }
    else if (ch.c === ' ') flush();
    else word.push(ch);
  }
  flush(); if (cur.length) lines.push(cur);
  lines.forEach(ln => { if (ln.length > maxC) notes.push(`mono line too long (${ln.length} > ${maxC}): "${ln.map(c => c.c).join('')}"`); });
  return lines;
}
function mono(x, y, markup, maxW, host) {
  const lines = monoLines(markup, maxW);
  lines.forEach((ln, i) => {
    const by = y + i * CODE_LH;
    let k = 0;
    while (k < ln.length) {
      let j = k; while (j < ln.length && ln[j].st === ln[k].st) j++;
      const s = ln.slice(k, j).map(c => c.c).join('').replace(/ /g, ' ');
      const st = ln[k].st, lead = s.length - s.trimStart().length, t = s.trim();
      const rx = x + (k + lead) * CHAR;
      if (st && t) f.raw(`<rect x="${(rx - 2).toFixed(1)}" y="${(by - CODE * 0.86).toFixed(1)}" width="${(t.length * CHAR + 4).toFixed(1)}" height="${(CODE * 1.18).toFixed(1)}" rx="3" fill="${st === 2 ? HL_WARN : HL}"/>`);
      if (t) T(rx, by, t, { size: CODE, family: MONO, weight: st ? 700 : 400, fill: st === 2 ? P.WARN_TEXT : P.INK }, host);
      k = j;
    }
  });
  return y + (lines.length - 1) * CODE_LH;
}

// ---- header ----
let y = 64;
T(M, y, 'WHAT THE MODEL READS AFTER A FAILED CALL', { size: 28, family: MONO, fill: P.GOLD_TEXT, spacing: 3 });
f.raw(`<line x1="${M}" y1="${y + 22}" x2="${WD - M}" y2="${y + 22}" stroke="${P.GOLD}" stroke-width="2"/>`);
y += 92;
T(M, y, 'The model fixed its call only when it could read the codes', { size: 46, weight: 700 });
y += 52;

// ---- top row: request, call, rejection ----
const TT = 26, TLH = 32, USER = 24, USER_LH = 31;
const TOP = [
  { kind: 'person', title: 'The user asks',
    sans: '“Open a high priority ticket: CSV export on the reports page times out for large date ranges.”' },
  { kind: 'service', title: 'gpt-6-astra calls the tool',
    mono: 'create_ticket\n{"title": "CSV export on reports page times out for large date ranges", "priority": ⦃"high"⦄}' },
  { kind: 'bad', title: 'The service rejects it',
    mono: `422 Unprocessable Entity\n"loc": ["body", ⁅"priority"⁆],\n"msg": "Input should be\n⁅'P0', 'P1' or 'P2'⁆",\n"input": "high"` },
];
const bodyH = (t, w) => t.sans ? f.wrap(t.sans, w, USER).length * USER_LH : monoLines(t.mono, w).length * CODE_LH;
const topH = Math.max(...TOP.map((t, i) => PAD + TLH + 10 + bodyH(t, COLW[i] - 2 * PAD))) + PAD - 4;
const topY = y;
const topBoxes = TOP.map((t, i) => {
  const k = A.KIND[t.kind], x = COLX[i], w = COLW[i];
  f.raw(`<rect x="${x}" y="${topY}" width="${w}" height="${topH}" rx="10" fill="${k.fill}" stroke="${k.stroke}" stroke-width="1.8"/>`);
  const r = rect(`top box ${i + 1}`, x, topY, w, topH);
  const ty = topY + PAD + TT * 0.8;
  if (f.width(t.title, TT, true) > w - 2 * PAD) notes.push(`top title too wide: "${t.title}"`);
  T(x + PAD, ty, t.title, { size: TT, weight: 700, fill: k.title }, r.name);
  const by = ty + 10 + TLH;
  if (t.sans) para(x + PAD, by, t.sans, w - 2 * PAD, USER, USER_LH, { fill: P.INK2 }, r.name);
  else mono(x + PAD, by, t.mono, w - 2 * PAD, r.name);
  return r;
});
const topMid = topY + topH / 2;
arrow([[topBoxes[0].x1, topMid], [topBoxes[1].x0, topMid]], 'top box 1', 'top box 2');
arrow([[topBoxes[1].x1, topMid], [topBoxes[2].x0, topMid]], 'top box 2', 'top box 3');
y = topY + topH;

// ---- the harness band ----
const ARROW_L = 42, bandH = 58, bandY = y + ARROW_L;
f.raw(`<rect x="${M}" y="${bandY}" width="${WD - 2 * M}" height="${bandH}" rx="12" fill="${P.COOL_FILL}" stroke="${P.COOL}" stroke-width="2"/>`);
rect('band', M, bandY, WD - 2 * M, bandH);
T(WD / 2, bandY + bandH / 2 + 10, 'The harness turns the error into the text the model reads next', { size: 28, weight: 700, fill: P.COOL, anchor: 'middle' }, 'band');
arrow([[C[2], y], [C[2], bandY]], 'top box 3', 'band');
y = bandY + bandH;

// ---- three cards: what the model reads ----
const CARDS = [
  { title: 'Fixed line', sub: 'SDK default since 0.23.1',
    text: 'An error occurred while running the tool. Please try again.' },
  // the field and the codes are marked wherever the model can read them, so the fixed line shows nothing marked
  { title: 'Old line plus the error', sub: 'SDK default in 0.22.3',
    text: `An error occurred while running the tool. Please try again. Error: 422 Unprocessable Entity: {"detail": [{"type": "enum", "loc": ["body", ⁅"priority"⁆], "msg": "Input should be ⁅'P0', 'P1' or 'P2'⁆", "input": "high", "ctx": {"expected": "'P0', 'P1' or 'P2'"}}]}` },
  { title: 'Approved note', sub: 'written by your team',
    text: `⁅priority⁆ is not valid. Allowed values: ⁅P0${NB}(critical)⁆, ⁅P1${NB}(high)⁆, ⁅P2${NB}(normal)⁆. Next step: call create_ticket again with priority set to one of these codes.` },
];
const cardY = y + ARROW_L;
const CT = 30, CS = 24;
const headH = PAD + CT * 1.2 + 6 + CS * 1.2 + 12;
const nLines = CARDS.map((c, i) => monoLines(c.text, COLW[i] - 2 * PAD).length);
const cardH = headH + 14 + CODE * 0.82 + (Math.max(...nLines) - 1) * CODE_LH + PAD + 2;
CARDS.forEach((c, i) => {
  const x = COLX[i], w = COLW[i];
  f.raw(`<rect x="${x}" y="${cardY}" width="${w}" height="${cardH}" rx="10" fill="#FFFFFF" stroke="${P.INK3}" stroke-width="1.8"/>`);
  const r = rect(`card ${i + 1}`, x, cardY, w, cardH);
  if (f.width(c.title, CT, true) > w - 2 * PAD) notes.push(`card title too wide: "${c.title}"`);
  T(x + PAD, cardY + PAD + CT * 0.8, c.title, { size: CT, weight: 700 }, r.name);
  T(x + PAD, cardY + PAD + CT * 1.2 + 6 + CS * 0.8, c.sub, { size: CS, fill: P.INK3 }, r.name);
  f.raw(`<line x1="${x + PAD}" y1="${cardY + headH}" x2="${x + w - PAD}" y2="${cardY + headH}" stroke="${P.RULE}" stroke-width="1.4"/>`);
  mono(x + PAD, cardY + headH + 14 + CODE * 0.82, c.text, w - 2 * PAD, r.name);
  arrow([[C[i], y], [C[i], cardY]], 'band', r.name);
});
y = cardY + cardH;

// ---- outcomes, from results.csv ----
y += 58;
T(M, y, 'Runs that created the ticket with P1, out of 20', { size: 30, weight: 700 });
y += 52;
const OUT = [
  { rows: [['gpt-6-astra', 0], ['Qwen3.5 2B', 0]], why: 'gpt-6-astra sent “high” again, then gave up' },
  { rows: [['gpt-6-astra', 20], ['Qwen3.5 2B', 1]], why: 'Qwen3.5 2B stored P0, the code for critical, in 19 runs' },
  { rows: [['gpt-6-astra', 20], ['Qwen3.5 2B', 20]], why: 'Both sent P1 on the second call' },
];
const RN = 38, RL = 48;
let outBot = y;
OUT.forEach((o, i) => {
  const x = COLX[i], w = COLW[i];
  o.rows.forEach(([m, n], j) => {
    const by = y + j * RL;
    T(x, by, m, { size: 26, fill: P.INK2 });
    T(x + w, by + 1, `${n} of 20`, { size: RN, weight: 700, fill: n === 20 ? P.GREEN : P.WARN_TEXT, anchor: 'end' });
  });
  outBot = Math.max(outBot, para(x, y + (o.rows.length - 1) * RL + 44, o.why, w, 24, 31, { fill: P.INK2 }));
});
y = outBot;

// ---- footer ----
y += 64;
// names the SDK the way run-results.png and the README do
const FOOT = 'Source: the experiment in this repo, on OpenAI Agents SDK 0.24.0, 20 runs per model and text.';
if (f.width(FOOT, 26) > WD - 2 * M) notes.push('footer longer than one line');
T(M, y, FOOT, { size: 26, fill: P.INK3 });

// ---- checks ----
const hit = (a, b, pad = 0) => a.x0 - pad < b.x1 && b.x0 < a.x1 + pad && a.y0 - pad < b.y1 && b.y0 < a.y1 + pad;
function check() {
  const out = [...notes];
  for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
    const p = texts[i], q = texts[j];
    // two style runs on one baseline may touch end to end, but not overlap
    const abut = p.base === q.base && (Math.abs(p.x1 - q.x0) < 0.5 || Math.abs(q.x1 - p.x0) < 0.5);
    if (!abut && hit(p, q)) out.push(`text overlap: "${p.s}" / "${q.s}"`);
  }
  for (const t of texts) {
    for (const r of rects) {
      if (t.host === r.name) {
        if (t.x0 < r.x0 + 12 || t.x1 > r.x1 - 12 || t.y0 < r.y0 + 8 || t.y1 > r.y1 - 8) out.push(`text not inside its ${r.name}: "${t.s}"`);
      } else if (hit(t, r, 10)) out.push(`text touches ${r.name}: "${t.s}"`);
    }
    if (t.x0 < M - 1 || t.x1 > WD - M + 1) out.push(`text outside the margins: "${t.s}"`);
    for (const g of segs) {
      const sr = { x0: Math.min(g.a[0], g.b[0]), y0: Math.min(g.a[1], g.b[1]), x1: Math.max(g.a[0], g.b[0]), y1: Math.max(g.a[1], g.b[1]) };
      if (hit(t, sr, 8)) out.push(`text touches an arrow (${g.from} to ${g.to}): "${t.s}"`);
    }
  }
  // outcome numbers must not crowd the model names in a narrow column
  for (const t of texts) for (const u of texts) if (t !== u && t.base === u.base && /of 20$/.test(u.s) && !/of 20$/.test(t.s) && t.x1 < u.x0 && u.x0 - t.x1 < 24) out.push(`number crowds its label: "${t.s}" / "${u.s}"`);
  for (const g of segs) {
    if (g.a[0] !== g.b[0] && g.a[1] !== g.b[1]) out.push(`diagonal arrow ${g.from} to ${g.to}`);
    const sr = { x0: Math.min(g.a[0], g.b[0]), y0: Math.min(g.a[1], g.b[1]), x1: Math.max(g.a[0], g.b[0]), y1: Math.max(g.a[1], g.b[1]) };
    for (const r of rects) if (r.name !== g.from && r.name !== g.to && hit(sr, r, -1)) out.push(`arrow ${g.from} to ${g.to} crosses ${r.name}`);
    const len = Math.hypot(g.b[0] - g.a[0], g.b[1] - g.a[1]);
    if (len < 36) out.push(`arrow ${g.from} to ${g.to} too short (${len})`);
  }
  for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++)
    if (hit(rects[i], rects[j], 20)) out.push(`boxes closer than 20 px: ${rects[i].name} / ${rects[j].name}`);
  if (COLW[1] < COLW[2]) out.push('middle column narrower than the note column');
  return out;
}

(async () => {
  const problems = check();
  const warn = await f.render('hero-what-the-model-read', [], process.env.OUT || undefined, { gap: 0 });
  const all = [...problems, ...warn];
  console.log('columns', COLW.map(Math.round).join(' / '));
  if (all.length) { console.log('GEOMETRY:\n  ' + all.join('\n  ')); process.exitCode = 1; }
  else console.log('geometry clean:', texts.length, 'texts,', rects.length, 'boxes,', segs.length, 'arrow segments');
})();
