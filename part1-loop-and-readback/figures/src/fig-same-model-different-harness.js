// Same model, different harness: Harness-Bench v2 average task scores for two models, each in seven agents.
// Numbers: arXiv 2605.27922v2 (revised 2026-10-15, the newest version on the abs page on 2026-10-27),
// Table 2 'General-task mean scores (274 tasks)', one decimal. Each value was read against its column header
// in the paper and cross-checked against Table 7 (two decimals) and the harness-bench.ai leaderboard data
// (general.configs, read 2026-10-27). All 14 match. The chart rows and the cross-check are in
// ../data/harness-bench-v2-chart-rows.csv.
// Score is the mean oracle score, partial credit 0 to 100, not a pass rate. Each pairing ran once, so the
// paper gives no interval per pairing and the chart draws none.
// GPT-5.6 Sol is the top model in the study and Qwen3.8-27B the bottom one (mean over the seven agents
// 70.67 and 52.77 in the JSON). Sol scores higher than Qwen in every agent (Sol low 66.5, Qwen high 65.1).
// Headline backs onto Section 5.1, 'Higher mean performance is associated with lower harness sensitivity'.
// Codex is OpenAI's own agent, so it carries the 'own agent' note under GPT-5.6 Sol. No harness here is
// Qwen's own, and Claude Code appears only as a harness (no Anthropic model is in the study).
// 1200 wide so it still reads at 400 px. Run: node fig-same-model-different-harness.js
const A = require('./arch');
const WD = 1200;
const f = A.fig(WD);
const { P } = f;
const MONO = 'Menlo, monospace';

// v: Table 7 / leaderboard JSON (two decimals), shown: Table 2 (one decimal). Rows sorted best first.
const PANELS = [
  { model: 'GPT-5.6 Sol', rows: [
    { agent: 'OpenClaw', v: 73.08, shown: '73.1' },
    { agent: 'Claude Code', v: 71.60, shown: '71.6' },
    { agent: 'Goose', v: 71.51, shown: '71.5' },
    { agent: 'Hermes', v: 71.18, shown: '71.2' },
    { agent: 'OpenCode', v: 71.03, shown: '71.0' },
    { agent: 'Codex', note: "OpenAI's own agent", v: 69.83, shown: '69.8' },
    { agent: 'Nanobot', v: 66.49, shown: '66.5' },
  ] },
  { model: 'Qwen3.8-27B', rows: [
    { agent: 'OpenCode', v: 65.10, shown: '65.1' },
    { agent: 'Codex', v: 62.42, shown: '62.4' },
    { agent: 'Hermes', v: 61.75, shown: '61.8' },
    { agent: 'Claude Code', v: 61.67, shown: '61.7' },
    { agent: 'OpenClaw', v: 58.32, shown: '58.3' },
    { agent: 'Nanobot', v: 34.25, shown: '34.3' },
    { agent: 'Goose', v: 25.91, shown: '25.9' },
  ] },
];

// ---- geometry trace ----
const boxes = []; const obst = []; const notes = [];
for (const p of PANELS) for (const r of p.rows)
  if (r.v.toFixed(1) !== r.shown) notes.push(`Table 2 and Table 7 disagree: ${p.model} ${r.agent}`);
function T(x, y, s, o = {}) {
  if (/[–—;]/.test(s)) notes.push(`dash or semicolon in figure text: "${s}"`);
  const size = o.size || 26;
  if (size < 26) notes.push(`text below 26 px: "${s}"`);
  const w = f.text(x, y, s, { ...o, size });
  const anchor = o.anchor || 'start';
  const x0 = anchor === 'middle' ? x - w / 2 : anchor === 'end' ? x - w : x;
  boxes.push({ s, x0, y0: y - size * 0.76, x1: x0 + w, y1: y + size * 0.24 });
  return w;
}
const ob = (what, x0, y0, x1, y1) => obst.push({ what, x0, y0, x1, y1 });
function para(x, y, s, maxW, size, lh, o = {}) {
  const ls = f.wrap(s, maxW, size, o.weight >= 600);
  if (ls.length > 1 && !/\s/.test(ls[ls.length - 1].trim())) notes.push(`one-word last line: "${ls[ls.length - 1]}"`);
  ls.forEach((t, i) => T(x, y + i * lh, t, { ...o, size }));
  return y + (ls.length - 1) * lh;
}

// ---- header ----
let y = 64;
T(60, y, 'SAME MODEL, DIFFERENT HARNESS', { size: 28, family: MONO, fill: P.GOLD_TEXT, spacing: 3 });
f.raw(`<line x1="60" y1="${y + 22}" x2="${WD - 60}" y2="${y + 22}" stroke="${P.GOLD}" stroke-width="2"/>`);
y += 92;
const HEAD = ['The harness matters far less', 'for the stronger model'];   // balanced by hand
HEAD.forEach((s, i) => T(60, y + i * 56, s, { size: 46, weight: 700 }));
y += (HEAD.length - 1) * 56 + 50;
// The task count and the partial-credit note live here, not in the footer, so the footer stays one short source line.
y = para(60, y, 'Average task score out of 100 when each model runs in seven different agents. '
  + 'Every agent got the same 274 work tasks, each scored with partial credit.',
  WD - 120, 30, 38, { fill: P.INK2 });
y += 40;

// ---- chart: lay out first, so the grid can go under everything ----
const XL = 360, XR = 1040, MAX = 100, STEP = 20, VX = WD - 60;   // VX: right edge of the value column
const xv = v => XL + (v / MAX) * (XR - XL);
const RH = 66, NOTE_RH = 86, PANEL_GAP = 44;   // a row with an 'own agent' note gets more room
const chartTop = y;
const L = PANELS.map((p, pi) => {
  const top = y + (pi > 0 ? PANEL_GAP : 0);
  const rowsTop = top + 72;
  let ry = rowsTop; const cys = [];
  for (const r of p.rows) { const h = r.note ? NOTE_RH : RH; cys.push(ry + h / 2); ry += h; }
  const rowsBot = ry;
  y = rowsBot;
  return { top, rowsTop, rowsBot, cys, rule: pi > 0 ? top - PANEL_GAP / 2 : null };
});
const chartBot = y + 8;
// band from each model's worst to best agent, then the grid on top of it, both under the dots.
// The grid runs only inside each panel's rows, so the titles and brackets sit on a clean ground.
L.forEach((g, pi) => {
  const vs = PANELS[pi].rows.map(r => r.v);
  f.raw(`<rect x="${xv(Math.min(...vs))}" y="${g.rowsTop - 6}" width="${xv(Math.max(...vs)) - xv(Math.min(...vs))}" height="${g.rowsBot - g.rowsTop + 6}" fill="${P.GOLD_FILL}"/>`);
  for (let t = 0; t <= MAX; t += STEP)
    f.raw(`<line x1="${xv(t)}" y1="${g.rowsTop - 6}" x2="${xv(t)}" y2="${g === L[L.length - 1] ? chartBot : g.rowsBot}" stroke="${t === 0 ? P.INK3 : P.RULE}" stroke-width="${t === 0 ? 1.6 : 1}"/>`);
});
for (let t = 0; t <= MAX; t += STEP) T(xv(t), chartBot + 36, `${t}`, { size: 28, fill: P.INK3, anchor: 'middle' });

PANELS.forEach((p, pi) => {
  const g = L[pi];
  if (g.rule != null) {
    f.raw(`<line x1="60" y1="${g.rule}" x2="${WD - 60}" y2="${g.rule}" stroke="${P.RULE}" stroke-width="1.4"/>`);
    ob('panel rule', 60, g.rule - 1, WD - 60, g.rule + 1);
  }
  const lo = Math.min(...p.rows.map(r => r.v)), hi = Math.max(...p.rows.map(r => r.v));
  const spread = (hi - lo).toFixed(1);
  const by = g.rowsTop - 16;
  // the model name and the spread label share one baseline (they were 2 px apart)
  T(60, by - 14, p.model, { size: 32, weight: 700 });
  f.raw(`<polyline points="${xv(lo)},${by + 10} ${xv(lo)},${by} ${xv(hi)},${by} ${xv(hi)},${by + 10}" fill="none" stroke="${P.GOLD_TEXT}" stroke-width="2"/>`);
  ob('bracket', xv(lo), by, xv(hi), by + 10);
  const label = `${spread} points from best to worst`;
  // centre the label on the bracket, but keep it inside the plot's right edge
  const lw = f.width(label, 28, true);
  const lx = Math.min((xv(lo) + xv(hi)) / 2, VX - lw / 2);
  T(lx, by - 14, label, { size: 28, weight: 700, fill: P.GOLD_TEXT, anchor: 'middle' });
  p.rows.forEach((r, i) => {
    const cy = g.cys[i];
    if (r.note) {
      T(60, cy - 6, r.agent, { size: 28 });
      T(60, cy + 27, r.note, { size: 28, fill: P.INK3 });
    } else T(60, cy + 10, r.agent, { size: 28 });
    const c = xv(r.v);
    f.raw(`<circle cx="${c}" cy="${cy}" r="11" fill="${P.COOL}" stroke="#FFFFFF" stroke-width="2.5"/>`);
    ob(`dot ${p.model} ${r.agent}`, c - 13, cy - 13, c + 13, cy + 13);
    T(VX, cy + 10, r.shown, { size: 28, weight: 700, anchor: 'end' });
  });
});
y = chartBot + 36;

// ---- footer ----
y += 64;
// One short source line. The partial-credit note is in the subtitle, and the version date is the one a reader needs.
// The footer names the paper only, never a table or figure number. The numbers are still read from Table 2 and
// checked against Table 7, as the header comment says.
const FOOT = ['Source: Harness-Bench (arXiv 2605.27922, revised Oct 15, 2026).'];
FOOT.forEach((s, i) => {
  if (f.width(s, 28) > WD - 120) notes.push(`footer line too long: "${s}"`);
  T(60, y + i * 37, s, { size: 28, fill: P.INK3 });
});

// ---- checks ----
function check() {
  const out = [...notes];
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const p = boxes[i], q = boxes[j];
    if (p.x0 < q.x1 && q.x0 < p.x1 && p.y0 < q.y1 && q.y0 < p.y1) out.push(`text overlap: "${p.s}" / "${q.s}"`);
  }
  for (const t of boxes) for (const o of obst)
    if (t.x0 - 4 < o.x1 && o.x0 < t.x1 + 4 && t.y0 - 4 < o.y1 && o.y0 < t.y1 + 4) out.push(`text touches the ${o.what}: "${t.s}"`);
  // row labels must stay left of the plot
  for (const t of boxes) if (t.x0 < XL && t.x1 > XL - 16 && t.y0 > chartTop && t.y1 < chartBot) out.push(`label runs into the plot: "${t.s}"`);
  // text must not sit on a grid line inside a panel's rows (the grid runs from rowsTop - 6 to rowsBot)
  for (const t of boxes) for (const g of L) if (t.y1 > g.rowsTop - 6 && t.y0 < g.rowsBot + 8)
    for (let v = 0; v <= MAX; v += STEP) if (t.x0 - 3 < xv(v) && t.x1 + 3 > xv(v)) out.push(`grid line ${v} crosses text: "${t.s}"`);
  // value column must clear the right edge of the plot and the last tick label
  for (const t of boxes) if (/^\d+\.\d$/.test(t.s) && t.x0 < xv(MAX) + 30) out.push(`value too close to the plot: "${t.s}"`);
  return out;
}

(async () => {
  const problems = check();
  const warn = await f.render('same-model-different-harness', [], process.env.OUT || undefined, { gap: 0 });
  const all = [...problems, ...warn];
  if (all.length) { console.log('GEOMETRY:\n  ' + all.join('\n  ')); process.exitCode = 1; }
  else console.log('geometry clean:', boxes.length, 'texts,', obst.length, 'marks');
})();
