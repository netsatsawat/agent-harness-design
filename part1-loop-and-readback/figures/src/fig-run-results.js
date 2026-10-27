// Run results: how 20 runs of each model ended under each of the three error texts, ticket task and phone task.
// Numbers: read at run time from ../../experiment/sweep/results.csv (sweep of 2026-10-27, openai-agents 0.24.0,
// 20 runs per cell). Each run has one outcome, graded on its FIRST accepted call (harness_defaults.py):
//   success      the first accepted call carried the right value (priority P1, phone exactly +14155550132)
//   wrong_value  the first accepted call carried a value the server accepted but the user did not ask for
//                (P0 on the ticket task, +4155550132 or +1415550132 on the phone task)
//   the rest     no accepted call before the run ended (gave_up, max_turns, no_call, model_error)
// The script checks that the three parts add up to the 20 runs and that wrong_other is 0 in every cell.
// Arms: default = the SDK's fixed line, old_default = the 0.22.3 line with the raw 422 error added,
// note = the approved note. The hero figure already says the services are made up, so this footer does not.
// Colours: COOL blue and WARN red from arch.js, checked as a pair on the cloth ground (#F4F1EA) for colour-vision
// deficiency: CVD dE 21.3, normal dE 26.7, both >= 3:1 contrast. Green and red failed (CVD dE 4.9).
// 1200 wide so it still reads at 400 px. Run: node fig-run-results.js
const fs = require('fs');
const path = require('path');
const A = require('./arch');
const WD = 1200;
const f = A.fig(WD);
const { P } = f;
const MONO = 'Menlo, monospace';
const TRACK = '#E3DCCC';   // the part of a bar where nothing was accepted, one step darker than WELL

// ---- data ----
const CSV = path.join(__dirname, '../../experiment/sweep/results.csv');
function parseCsv(s) {
  const rows = []; let row = [], cur = '', q = false;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (q) { if (c === '"' && s[i + 1] === '"') { cur += '"'; i++; } else if (c === '"') q = false; else cur += c; }
    else if (c === '"') q = true;
    else if (c === ',') { row.push(cur); cur = ''; }
    else if (c === '\n') { row.push(cur); rows.push(row); row = []; cur = ''; }
    else if (c !== '\r') cur += c;
  }
  if (cur || row.length) { row.push(cur); rows.push(row); }
  const [h, ...body] = rows;
  return body.filter(r => r.length === h.length).map(r => Object.fromEntries(h.map((k, i) => [k, r[i]])));
}
const rows = parseCsv(fs.readFileSync(CSV, 'utf8'));
const MODELS = [
  ['qwen3.5:0.8b', 'Qwen3.5 0.8B'], ['qwen3.5:2b', 'Qwen3.5 2B'], ['qwen3.5:4b', 'Qwen3.5 4B'],
  ['qwen3.5:9b', 'Qwen3.5 9B'], ['gpt-6-astra', 'gpt-6-astra'], ['gpt-6.1-sol', 'gpt-6.1-sol'],
];
const TASKS = [
  { key: 'priority', title: 'Ticket priority', sub: ['The fix needs codes', 'only the server knows'] },   // broken by hand
  { key: 'phone', title: 'Phone number', sub: ['A model can work out', 'the right format'] },
];
const ARMS = [
  { key: 'default', name: 'Fixed line:', desc: '“An error occurred while running the tool. Please try again.”' },
  { key: 'old_default', name: 'Old line:', desc: "the 0.22.3 default, which adds the server's raw error" },
  { key: 'note', name: 'Approved note:', desc: 'the field, the allowed values with their meaning, the next step' },
];
const notes = [];
const cell = (m, t, a) => {
  const r = rows.find(x => x.model === m && x.task === t && x.arm === a);
  if (!r) { notes.push(`missing cell ${m} ${t} ${a}`); return { ok: 0, wrong: 0, n: 20 }; }
  const n = +r.runs, ok = +r.success, wrong = +r.wrong_value;
  const rest = +r.gave_up + +r.max_turns + +r.no_call + +r.model_error;
  if (+r.wrong_other !== 0) notes.push(`wrong_other is not 0: ${m} ${t} ${a}`);
  if (ok + wrong + rest !== n) notes.push(`outcomes do not add up to runs: ${m} ${t} ${a}`);
  if (n !== 20) notes.push(`not 20 runs: ${m} ${t} ${a}`);
  return { ok, wrong, n };
};

// ---- geometry trace ----
const boxes = []; const obst = [];
function T(x, y, s, o = {}) {
  if (/[–—;]/.test(s)) notes.push(`dash or semicolon in figure text: "${s}"`);
  const size = o.size || 28;
  if (size < 26) notes.push(`text below 26 px: "${s}"`);
  const w = f.text(x, y, s, { ...o, size });
  const anchor = o.anchor || 'start';
  const x0 = anchor === 'middle' ? x - w / 2 : anchor === 'end' ? x - w : x;
  // digits and capitals have no descender, so their box ends at the baseline
  const desc = /^[0-9A-Z +.]+$/.test(s) ? 0.02 : 0.24;
  boxes.push({ s, x0, y0: y - size * 0.76, x1: x0 + w, y1: y + size * desc, inside: o.inside });
  return w;
}
const ob = (what, x0, y0, x1, y1) => obst.push({ what, x0, y0, x1, y1 });
function para(x, y, s, maxW, size, lh, o = {}) {
  const ls = f.wrap(s, maxW, size, o.weight >= 600);
  if (ls.length > 1 && !/\s/.test(ls[ls.length - 1].trim())) notes.push(`one-word last line: "${ls[ls.length - 1]}"`);
  ls.forEach((t, i) => T(x, y + i * lh, t, { ...o, size }));
  return y + (ls.length - 1) * lh;
}
// a rect with only its right corners rounded (the data end), square at the baseline
function bar(x, y, w, h, fill, roundRight) {
  if (w <= 0) return;
  const r = roundRight ? Math.min(4, w / 2) : 0;
  f.raw(`<path d="M${x},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h - r} Q${x + w},${y + h} ${x + w - r},${y + h} H${x} Z" fill="${fill}"/>`);
}

// ---- header ----
let y = 64;
T(60, y, 'SIX MODELS, THREE ERROR TEXTS', { size: 28, family: MONO, fill: P.GOLD_TEXT, spacing: 3 });
f.raw(`<line x1="60" y1="${y + 22}" x2="${WD - 60}" y2="${y + 22}" stroke="${P.GOLD}" stroke-width="2"/>`);
y += 92;
// 'got right', not 'fixed', so the headline does not clash with the 'Fixed line' row name
const HEAD = ["Without the server's codes, no model got", 'more than 1 of 20 ticket runs right'];   // balanced by hand
HEAD.forEach((s, i) => T(60, y + i * 56, s, { size: 46, weight: 700 }));
y += (HEAD.length - 1) * 56 + 50;
y = para(60, y, 'How 20 runs of each model ended, by the text the model read after a rejected call. The number beside each bar counts the runs with the right value.',
  WD - 120, 30, 38, { fill: P.INK2 });
y += 52;

// ---- legend: one swatch per outcome, in the order the parts sit on a bar ----
const LEG = [
  { fill: P.COOL, label: 'Right value accepted' },
  { fill: P.WARN, label: 'Wrong value accepted, which looks like success in a trace',
    more: 'P0 on the ticket task, a wrong number on the phone task' },
  { fill: TRACK, label: 'Nothing accepted before the run ended' },
];
LEG.forEach((g, i) => {
  const cy = y - 9;
  bar(60, cy - 11, 44, 22, g.fill, true);
  ob(`legend swatch ${i}`, 60, cy - 11, 104, cy + 11);
  T(120, y, g.label, { size: 28, fill: P.INK });
  if (g.more) { y += 36; T(120, y, g.more, { size: 28, fill: P.INK2 }); }
  if (i < LEG.length - 1) y += 44;
});
y += 66;

// ---- columns ----
const LW = Math.max(...MODELS.map(([, l]) => f.width(l, 28)));
const X0 = [Math.round(60 + LW + 32)];
const VALW = 44, PGAP = 72;   // the gap keeps a value with its own bar, not the next panel
const TW = Math.floor((WD - 60 - X0[0] - 2 * VALW - PGAP) / 2);   // track width
X0.push(X0[0] + TW + VALW + PGAP);
const VX = X0.map(x => x + TW + VALW);   // right edge of each value column
const U = TW / 20;
const xv = (pi, n) => X0[pi] + n * U;

// panel titles
let ty = y;
TASKS.forEach((t, pi) => {
  T(X0[pi], ty, t.title, { size: 30, weight: 700 });
  t.sub.forEach((s, i) => {
    if (f.width(s, 28) > VX[pi] - X0[pi]) notes.push(`panel subtitle wider than its panel: "${s}"`);
    T(X0[pi], ty + 40 + i * 34, s, { size: 28, fill: P.INK2 });
  });
});
const subLines = Math.max(...TASKS.map(t => t.sub.length));
y = ty + 40 + (subLines - 1) * 34 + 30;

// ---- blocks, one per error text ----
const RH = 40, BH = 22, GROUP_GAP = 10, BLOCK_GAP = 34;
const blocks = [];
ARMS.forEach((arm, ai) => {
  y += ai === 0 ? 36 : BLOCK_GAP + 36;
  const hw = f.width(arm.name, 28, true);
  const one = hw + 14 + f.width(arm.desc, 28) <= WD - 120;
  const hy = y;
  T(60, y, arm.name, { size: 28, weight: 700 });
  if (one) T(60 + hw + 14, y, arm.desc, { size: 28, fill: P.INK2 });
  else { y += 36; para(60, y, arm.desc, WD - 120, 28, 36, { fill: P.INK2 }); }
  const rowsTop = y + 20;
  let ry = rowsTop; const cys = [];
  MODELS.forEach((m, mi) => { if (mi === 4) ry += GROUP_GAP; cys.push(ry + RH / 2); ry += RH; });
  blocks.push({ arm, hy, rowsTop, rowsBot: ry, cys });
  y = ry;
});
const chartBot = y;

// bars: track, then the grid over the track, then the data on top
blocks.forEach(b => {
  TASKS.forEach((t, pi) => {
    MODELS.forEach(([mk], mi) => {
      const c = cell(mk, t.key, b.arm.key);
      const by = b.cys[mi] - BH / 2;
      const a = c.ok, w = c.ok + c.wrong;
      // nothing accepted: from the end of the data to 20, with a 2px gap after the data
      if (w < 20) bar(xv(pi, w) + (w > 0 ? 1 : 0), by, (20 - w) * U - (w > 0 ? 1 : 0), BH, TRACK, true);
      ob(`bar ${mk} ${t.key} ${b.arm.key}`, X0[pi], by, X0[pi] + TW, by + BH);
    });
    for (let v = 0; v <= 20; v += 5) {
      f.raw(`<line x1="${xv(pi, v)}" y1="${b.rowsTop - 4}" x2="${xv(pi, v)}" y2="${b.rowsBot + 4}" stroke="${v === 0 ? P.INK3 : P.RULE}" stroke-width="${v === 0 ? 1.6 : 1}"/>`);
    }
    MODELS.forEach(([mk], mi) => {
      const c = cell(mk, t.key, b.arm.key);
      const by = b.cys[mi] - BH / 2;
      const a = c.ok, w = c.ok + c.wrong;
      // right value: from 0, square at the baseline, round at its end unless a wrong part follows
      if (a > 0) bar(xv(pi, 0), by, a * U - (a < 20 ? 1 : 0), BH, P.COOL, c.wrong === 0);
      // wrong value: after a 2px gap, round at its end
      if (c.wrong > 0) {
        const x = xv(pi, a) + (a > 0 ? 1 : 0), ww = c.wrong * U - (a > 0 ? 1 : 0) - (w < 20 ? 1 : 0);
        bar(x, by, ww, BH, P.WARN, true);
        const lbl = String(c.wrong);
        if (f.width(lbl, 26, true) + 16 <= ww)
          T(x + ww / 2, b.cys[mi] + 9, lbl, { size: 26, weight: 700, fill: '#FFFFFF', anchor: 'middle', inside: true });
      }
      T(VX[pi], b.cys[mi] + 10, String(c.ok), { size: 28, weight: 700, anchor: 'end' });
    });
  });
  MODELS.forEach(([, label], mi) => T(60, b.cys[mi] + 10, label, { size: 28 }));
});

// axis under each panel
y = chartBot + 40;
TASKS.forEach((t, pi) => {
  for (let v = 0; v <= 20; v += 5) T(xv(pi, v), y, String(v), { size: 28, fill: P.INK3, anchor: 'middle' });
  T(xv(pi, 10), y + 38, 'Runs out of 20', { size: 28, fill: P.INK3, anchor: 'middle' });
});
y += 38;

// ---- footer: one short source line ----
y += 70;
const FOOT = 'Source: the experiment in this repo, on OpenAI Agents SDK 0.24.0, Oct 27, 2026.';
if (f.width(FOOT, 28) > WD - 120) notes.push(`footer line too long: "${FOOT}"`);
T(60, y, FOOT, { size: 28, fill: P.INK3 });

// ---- checks ----
function check() {
  const out = [...notes];
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const p = boxes[i], q = boxes[j];
    if (p.x0 < q.x1 && q.x0 < p.x1 && p.y0 < q.y1 && q.y0 < p.y1) out.push(`text overlap: "${p.s}" / "${q.s}"`);
  }
  for (const t of boxes) if (!t.inside) for (const o of obst)
    if (t.x0 - 4 < o.x1 && o.x0 < t.x1 + 4 && t.y0 - 4 < o.y1 && o.y0 < t.y1 + 4) out.push(`text touches the ${o.what}: "${t.s}"`);
  // a label inside a bar must sit fully inside that bar
  for (const t of boxes) if (t.inside && !obst.some(o => t.x0 >= o.x0 && t.x1 <= o.x1 && t.y0 >= o.y0 - 2 && t.y1 <= o.y1 + 2))
    out.push(`in-bar label escapes its bar: "${t.s}"`);
  // text must not sit on a grid line inside a block's rows
  for (const t of boxes) if (!t.inside) for (const b of blocks) if (t.y1 > b.rowsTop - 4 && t.y0 < b.rowsBot + 4)
    for (let pi = 0; pi < 2; pi++) for (let v = 0; v <= 20; v += 5)
      if (t.x0 - 3 < xv(pi, v) && t.x1 + 3 > xv(pi, v)) out.push(`grid line ${v} crosses text: "${t.s}"`);
  // value columns must clear the end of their own track and the start of the next panel
  for (const t of boxes) if (/^\d+$/.test(t.s) && !t.inside && t.y0 > blocks[0].rowsTop - 4 && t.y1 < chartBot + 4) {
    const pi = t.x1 > X0[1] ? 1 : 0;
    if (t.x0 < X0[pi] + TW + 8) out.push(`value too close to its bar: "${t.s}"`);
    if (pi === 0 && t.x1 > X0[1] - 30) out.push(`value too close to the next panel: "${t.s}"`);
  }
  return out;
}

(async () => {
  const problems = check();
  const warn = await f.render('run-results', [], process.env.OUT || undefined, { gap: 0 });
  const all = [...problems, ...warn];
  if (all.length) { console.log('GEOMETRY:\n  ' + all.join('\n  ')); process.exitCode = 1; }
  else console.log('geometry clean:', boxes.length, 'texts,', obst.length, 'marks', `X0=${X0} TW=${TW} VX=${VX}`);
})();
