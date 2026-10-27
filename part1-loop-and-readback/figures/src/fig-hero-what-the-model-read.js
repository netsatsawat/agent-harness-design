// Hero for Part 1: the setup, one failed create_ticket call, then the three texts the agent framework can send back,
// each with what it led to. Every string and number here was read from the experiment, not typed from memory:
//   user request    ../../experiment/harness_defaults.py, TASKS['priority'].prompt
//   the codes       ../../experiment/servers.py ticket_server: "Accepts only the codes P0 (critical), P1 (high), P2 (normal)."
//   right call      harness_defaults.py TASKS['priority'] answer "P1"
//   field text      harness_defaults.py create_ticket docstring, Args section: "priority: Priority for the ticket."
//                   The SDK puts it in the parameter schema as the priority field's description. (The tool's own
//                   description is "Create a support ticket.", so the setup names the field, not the tool.)
//   the call        ../../experiment/sweep/runs.jsonl, gpt-6-astra priority runs, calls[0].arguments as the model sent it (no spaces):
//                   {"title":"CSV export on reports page times out for large date ranges","priority":"high"}
//                   (that exact title in 58 of its 60 priority runs, priority "high" in all 60)
//   qwen first call ../../experiment/sweep/results.csv first_call_values for qwen3.5:2b priority: High:12 high:8 in every arm
//   the 422 body    ../../experiment/servers.py ticket_server, as logged in runs.jsonl server_error. The red box shows only
//                   loc, msg and input and says "(trimmed)". Card 2 cuts only the ctx part (it repeats msg) and says so.
//   fixed line      openai-agents 0.24.0 agents/tool.py default_tool_error_function (../../experiment/sdk_defaults.txt)
//   old line        the 0.22.3 default, the exact string runs.jsonl logs as model_read in the old_default arm.
//                   harness_defaults.py runs it on 0.24.0 as a copy of the 0.22.3 handler (failure_error_function),
//                   checked against the real 0.22.3 by check_error_strings.py. The footer says so.
//   approved note   harness_defaults.py APPROVED_NOTES['priority'], as logged in the note arm
//   outcomes        ../../experiment/sweep/results.csv rows priority x {default, old_default, note}:
//                   gpt-6-astra 0, 20, 20 of 20. qwen3.5:2b 0, 1, 20 of 20 (old line: wrong_value 19, P0:19).
//                   From runs.jsonl, fixed line: astra sent "high" on all 59 calls (all rejected) and gave up in all 20.
//                   qwen 2b sent High 74, high 30, HIGH 1, High Priority 1, HIGH PRIORITY 1, and 3 calls with no
//                   arguments (107 rejected, 3 not invoked), gave up in 15 and hit the turn limit in 5. Neither model
//                   sent a code on any call, so the card says "Neither model ever sent a code". Every old-line and
//                   note run of both models made exactly two calls, the second one P1 (P0 in 19 qwen 2b old-line runs,
//                   all accepted, so 19 tickets were filed as P0).
//   versions        0.23.1 first shipped the fixed line on PyPI, 0.22.3 is the last with the error text (sdk_defaults.txt, section 3).
//                   sdk_version is 0.24.0 on all 120 runs shown. The version numbers live in the footer only.
//   exception text  the 0.22.3 default appends str(error) (sdk_defaults.txt section 3). Here that holds the 422 body
//                   because servers.py raises it that way. A raise_for_status() client would carry only the status
//                   line and the URL (sdk_defaults.txt caveat), so card 2 says "the exception text", not "server error".
//   model names     two hosted OpenAI models, gpt-6-astra and gpt-6.1-sol, and four small local models (qwen3.5
//                   through Ollama, harness_defaults.py). The figure writes qwen3.5:2b as Qwen3.5 2B, as the README does.
// The service is made up for the test. The footer says so once, and the README caption repeats it.
// Design (2026-10-27, after a cold read found P0, P1 and P2 hard to follow with no background): a setup strip first
// (the request, the codes and their meaning, what the tool's description tells the model), then the failed call, then
// one card per text, read top to bottom: a heading that names the behaviour first and the SDK version second (so a
// LangGraph or Strands reader can place their own framework), the text itself, and a results strip right under it.
// Round 2: the title covers both halves (the codes alone fixed only gpt-6-astra), the flow boxes are balanced by line
// count, card 2 trims the repeated ctx part, the grey and gold text are one step darker, "reads" appears once.
// Round 3: card headings name what the text contains (a LangGraph or Strands reader matches their own framework's
// text, not a version), a grey line under each says who ships it, the versions moved to the footer, the title names
// P0, P1 and P2, the setup shows only the codes as accepted (meanings in lighter text), the right call has its own
// row, card 2 keeps the one space before "Error:" instead of a forced break, highlights pad only next to a space.
// Width is 1200, not 1400, so the type is larger at Medium's sizes: about 700 px in the column, 400 px on a phone.
// Layout is flow: every block anchors to the computed bottom of the one above. The checker at the end fails the build on
// text overlap, text outside its box, text on an arrow or box it does not belong to, arrows through boxes, boxes outside
// their parent box, small type (also at 400 px wide for the title, the setup, the card headings and the outcome numbers),
// empty space at the foot of a box, dashes or semicolons. Menlo advance is 0.602 em, Helvetica from helv_widths.json.
// Run: node fig-hero-what-the-model-read.js   (OUT=dir writes the PNG elsewhere, DUMP=dir also writes the SVG)
const A = require('./arch');
const WD = 1200;
const f = A.fig(WD);
const { P } = f;
const MONO = 'Menlo, monospace';
const M = 60, PAD = 20;
const CODE = 22, CODE_LH = 30, CHAR = CODE * 0.602;
const HL = '#F5E2B0', HL_WARN = '#F6D5CC';               // marker tints behind highlighted code
const GREY = '#57524A', GOLD_INK = '#654A0D';            // one step darker than INK3 and GOLD_TEXT, for text on cream
const NB = '\u00A0';                                      // keeps a code and its meaning on one line
const MIN_SANS = 24, MIN_MONO = 22;                      // at 1200 wide: 14 px and 12.8 px when Medium shows 700 px
const KEY_AT_400 = 9.3;                                  // px: title, setup, headings, outcome numbers on a 400 px phone
const MAX_SLACK = 40;                                    // most empty space allowed under the content of a box

// ---- geometry trace ----
const texts = [], rects = [], segs = [], notes = [];
function T(x, y, s, o = {}, host = null, tag = {}) {
  if (/[–—;]/.test(s)) notes.push(`dash or semicolon in figure text: "${s}"`);
  if (/schematic|\bI ran\b|\bbill\b/i.test(s)) notes.push(`banned word in figure text: "${s}"`);
  const size = o.size || 26, isMono = o.family === MONO, min = isMono ? MIN_MONO : MIN_SANS;
  if (size < min) notes.push(`text below ${min} px: "${s}"`);
  if (o.key && size * 400 / WD < KEY_AT_400) notes.push(`key text below ${KEY_AT_400} px at 400 px wide: "${s}"`);
  const w = f.text(x, y, s, { ...o, size }) + (o.spacing || 0) * [...s].length;
  const anchor = o.anchor || 'start';
  const x0 = anchor === 'middle' ? x - w / 2 : anchor === 'end' ? x - w : x;
  texts.push({ s, x0, y0: y - size * 0.76, x1: x0 + w, y1: y + size * 0.24, host, base: y, ...tag });
  return w;
}
function rect(name, x, y, w, h, parent = null) {
  const r = { name, x0: x, y0: y, x1: x + w, y1: y + h, parent }; rects.push(r); return r;
}
function box(name, x, y, w, h, fill, stroke, sw = 1.8, parent = null, rx = 10) {
  f.raw(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`);
  return rect(name, x, y, w, h, parent);
}
const ancestors = name => {
  const out = []; let r = rects.find(q => q.name === name);
  while (r && r.parent) { out.push(r.parent); r = rects.find(q => q.name === r.parent); }
  return out;
};
function para(x, y, s, maxW, size, lh, o = {}, host = null, tag = {}) {
  const ls = f.wrap(s, maxW, size, o.weight >= 600);
  if (ls.length > 1 && !/\s/.test(ls[ls.length - 1].trim())) notes.push(`one-word last line: "${ls[ls.length - 1]}"`);
  ls.forEach((t, i) => T(x, y + i * lh, t, { ...o, size }, host, tag));
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
  lines.forEach((ln, i) => {
    const s = ln.map(c => c.c).join('');
    if (ln.length > maxC) notes.push(`mono line too long (${ln.length} > ${maxC}): "${s}"`);
    // a code and its meaning stay on one line (round 2 caught "P2" / "(normal)" split when NB lost its byte)
    const next = lines[i + 1] ? lines[i + 1].map(c => c.c).join('') : '';
    if (/P[0-2]$/.test(s) && next.startsWith('(')) notes.push(`code split from its meaning: "${s}" / "${next}"`);
  });
  return lines;
}
const marks = [];                                        // highlight rectangles, checked against their neighbours
function mono(x, y, markup, maxW, host, tag = {}) {
  const lines = monoLines(markup, maxW);
  lines.forEach((ln, i) => {
    const by = y + i * CODE_LH;
    let k = 0;
    while (k < ln.length) {
      let j = k; while (j < ln.length && ln[j].st === ln[k].st) j++;
      const s = ln.slice(k, j).map(c => c.c).join('').replace(/\u00A0/g, ' ');
      const st = ln[k].st, lead = s.length - s.trimStart().length, t = s.trim();
      const rx = x + (k + lead) * CHAR;
      if (st && t) {
        // pad 2 px only on a side that faces a space: flush with the text column at a line start, and never
        // over the next character when punctuation follows (round 2 QA: '"priority"]' and ''P2'"' were touched)
        const a = k + lead, e = a + t.length;
        const pl = ln[a - 1] && ln[a - 1].c === ' ' ? 2 : 0, pr = ln[e] && ln[e].c === ' ' ? 2 : 0;
        const m = { x0: rx - pl, x1: rx + t.length * CHAR + pr, y0: by - CODE * 0.86, base: by, col: x, s: t };
        marks.push(m);
        f.raw(`<rect x="${m.x0.toFixed(1)}" y="${m.y0.toFixed(1)}" width="${(m.x1 - m.x0).toFixed(1)}" height="${(CODE * 1.18).toFixed(1)}" rx="3" fill="${st === 2 ? HL_WARN : HL}"/>`);
      }
      if (t) T(rx, by, t, { size: CODE, family: MONO, weight: st ? 700 : 400, fill: st === 2 ? P.WARN_TEXT : P.INK }, host, tag);
      k = j;
    }
  });
  return { last: y + (lines.length - 1) * CODE_LH, lastW: lines.length ? lines[lines.length - 1].length * CHAR : 0 };
}

// ---- header ----
let y = 60;
T(M, y, 'AFTER A FAILED TOOL CALL', { size: 24, family: MONO, fill: GOLD_INK, spacing: 3 });
f.raw(`<line x1="${M}" y1="${y + 20}" x2="${WD - M}" y2="${y + 20}" stroke="${P.GOLD}" stroke-width="2"/>`);
y += 78;
// the codes alone fixed gpt-6-astra (card 2), the small model also needed what they mean (card 3). The title names
// the codes, so a cold scan does not meet "the codes" before the setup box defines them.
// round 4: 'Both models ... only when' read per model clashed with card 2 (gpt-6-astra 20 of 20 on the codes alone).
// Leading with 'Only' makes it a joint claim, and 'note' matches the card 3 heading.
const TITLE = ['Only a note that said what P0, P1 and P2 mean', 'got both models to file the ticket as P1'], TS = 44, TLH = 52;
TITLE.forEach((s, i) => {
  if (f.width(s, TS, true) > WD - 2 * M) notes.push(`title line too long: "${s}"`);
  T(M, y + i * TLH, s, { size: TS, weight: 700, key: true });
});
y += (TITLE.length - 1) * TLH;

// ---- setup: the request, the codes and what they mean, the right call, what the field's description says ----
// Only the codes sit in chips, so a quick reader does not take "critical" or "high" for accepted values. The meanings
// follow each chip in lighter text. Read in order, the rows lead into the call below: the user wants high, the service
// wants P1, and the only text about the field gives no hint of the codes.
const SZ = 28, SLH = 38, SPAD = 24;
const REQ = '“Open a high priority ticket: CSV export on the reports page times out for large date ranges.”';
const LBL = ['User asks', 'Service accepts only', 'Correct call', 'Tool schema'];   // round 4: no templated 'The ...'
const CODES = [['P0', 'critical'], ['P1', 'high'], ['P2', 'normal']];
const RIGHT = 'P1', RIGHT_CALL = '"priority":"P1"';     // written the way the call below writes "high"
const TOOL = 'describes priority only as “Priority for the ticket.”';
const labW = Math.max(...LBL.map(s => f.width(s, SZ, true)));
const sx = M + SPAD, scx = sx + labW + 26, scW = WD - M - SPAD - scx;
const reqLines = f.wrap(REQ, scW, SZ);
const toolLines = f.wrap(TOOL, scW, SZ);
const CHIP_H = 50, CHIP_PAD = 14, MEAN_GAP = 12, CHIP_GAP = 30;
const chipW = CODES.map(([c]) => Math.ceil(CHIP_PAD + c.length * SZ * 0.602 + CHIP_PAD));
const chipsW = CODES.reduce((s, [, m], i) => s + chipW[i] + MEAN_GAP + f.width(m, SZ), 0) + CHIP_GAP * (CODES.length - 1);
if (chipsW > scW) notes.push(`setup codes row too wide: ${Math.round(chipsW)} > ${Math.round(scW)}`);
y += 40;
const setupY = y;
const b1 = setupY + SPAD + SZ * 0.76 + 4;
const b2 = b1 + (reqLines.length - 1) * SLH + SLH + 22;
const b3 = b2 + SLH + 20;
const b4 = b3 + SLH + 10;                                // same air between rows as around the chips
const setupH = Math.ceil(b4 + (toolLines.length - 1) * SLH + SZ * 0.24 + SPAD + 2 - setupY);
box('setup', M, setupY, WD - 2 * M, setupH, P.GOLD_FILL, P.GOLD, 2);
T(sx, b1, LBL[0], { size: SZ, weight: 700, key: true }, 'setup');
reqLines.forEach((s, i) => T(scx, b1 + i * SLH, s, { size: SZ, key: true }, 'setup'));
T(sx, b2, LBL[1], { size: SZ, weight: 700, key: true }, 'setup');
let chx = scx;
CODES.forEach(([c, m], i) => {
  const right = c === RIGHT, name = `chip ${c}`;
  box(name, chx, b2 - 35, chipW[i], CHIP_H, right ? P.GREEN_FILL : '#FFFFFF', right ? P.GREEN : P.INK3, right ? 2.4 : 1.6, 'setup', 8);
  T(chx + CHIP_PAD, b2, c, { size: SZ, family: MONO, weight: 700, fill: right ? P.GREEN : P.INK, key: true }, name);
  const mw = T(chx + chipW[i] + MEAN_GAP, b2, m, { size: SZ, fill: GREY, key: true }, 'setup');
  chx += chipW[i] + MEAN_GAP + mw + CHIP_GAP;
});
T(sx, b3, LBL[2], { size: SZ, weight: 700, key: true }, 'setup');
T(scx, b3, RIGHT_CALL, { size: SZ, family: MONO, weight: 700, fill: P.GREEN, key: true }, 'setup');
T(sx, b4, LBL[3], { size: SZ, weight: 700, key: true }, 'setup');
toolLines.forEach((s, i) => T(scx, b4 + i * SLH, s, { size: SZ, key: true }, 'setup'));
y = setupY + setupH;

// ---- the failed call: the model's call, the service's answer ----
// Widths are set so the two boxes hold the same number of lines: 4 code lines and a 2-line note on the left,
// 5 code lines and a 1-line note on the right. The checker fails the build if either box has a gap at its foot.
const FT = 28, NOTE = 24, NOTE_LH = 31;
const FLOW = [
  { name: 'call', kind: 'service', title: 'Both models call the tool',
    mono: 'create_ticket\n{"title":"CSV export on reports page\ntimes out for large date ranges",\n"priority":⦃"high"⦄}',
    after: 'Shown: gpt-6-astra’s call. Qwen3.5 2B also sent “high” or “High”.', afterFill: GREY },
  { name: 'reject', kind: 'bad', title: 'The service rejects it', aside: '(trimmed)',
    mono: `422 Unprocessable Entity\n"loc": ["body", ⁅"priority"⁆],\n"msg": "Input should be\n⁅'P0', 'P1' or 'P2'⁆",\n"input": "high"`,
    after: 'It lists the codes, but not what they mean.', afterFill: P.WARN_TEXT },
];
const RW = 496, FGAP = 64;
const FW = [WD - 2 * M - RW - FGAP, RW], FX = [M, M + FW[0] + FGAP];
const flowInner = (b, i) => {
  const n = monoLines(b.mono, FW[i] - 2 * PAD).length;
  const na = f.wrap(b.after, FW[i] - 2 * PAD, NOTE).length;
  return FT * 0.76 + 14 + CODE * 0.76 + (n - 1) * CODE_LH + 40 + (na - 1) * NOTE_LH + NOTE * 0.24;
};
y += 50;
const flowY = y;
const flowH = Math.ceil(Math.max(...FLOW.map(flowInner)) + 2 * PAD + 4);
const flowBoxes = FLOW.map((b, i) => {
  const k = A.KIND[b.kind], x = FX[i], w = FW[i];
  const r = box(b.name, x, flowY, w, flowH, k.fill, k.stroke);
  const tb = flowY + PAD + FT * 0.76 + 2;
  const tW = T(x + PAD, tb, b.title, { size: FT, weight: 700, fill: k.title }, b.name);
  if (b.aside && tW + 16 + f.width(b.aside, 24) > w - 2 * PAD) notes.push(`flow title and aside too wide: "${b.title}"`);
  if (b.aside) T(x + w - PAD, tb, b.aside, { size: 24, fill: GREY, anchor: 'end' }, b.name);
  const { last } = mono(x + PAD, tb + 14 + CODE * 0.76 + 4, b.mono, w - 2 * PAD, b.name);
  para(x + PAD, last + 40, b.after, w - 2 * PAD, NOTE, NOTE_LH, { fill: b.afterFill }, b.name);
  return r;
});
const flowMid = flowY + flowH / 2;
arrow([[flowBoxes[0].x1, flowMid], [flowBoxes[1].x0, flowMid]], 'call', 'reject');
y = flowY + flowH;

// ---- the agent framework band ----
const ARROW_L = 44, bandH = 60, bandY = y + ARROW_L;
box('band', M, bandY, WD - 2 * M, bandH, P.COOL_FILL, P.COOL, 2, null, 12);
T(WD / 2, bandY + bandH / 2 + 11, 'The framework picks one of these texts for the model to read next', { size: 30, weight: 700, fill: P.COOL, anchor: 'middle', key: true }, 'band');
const rejCx = (flowBoxes[1].x0 + flowBoxes[1].x1) / 2;
arrow([[rejCx, y], [rejCx, bandY]], 'reject', 'band');
y = bandY + bandH;

// ---- one card per text, read top to bottom: what it is, the text itself, what happened ----
// Headings name what the text contains, so a reader on LangGraph, Strands or anything else can match the text their
// own framework sends. The grey line under each says who ships it. Version numbers are in the footer only.
// Headings also tell the three texts apart at 400 px, where the code cannot be read.
const OPTS = [
  { head: 'A generic retry line', who: 'The framework hides the exception. The current OpenAI Agents SDK default.',
    text: 'An error occurred while running the tool. Please try again.',
    res: [['gpt-6-astra', 0], ['Qwen3.5 2B', 0]], why: 'Neither model ever sent a code, so every retry failed' },
  // the field and the codes are marked wherever the model can read them. The cut ctx part repeats the codes.
  // One space before "Error:", as in the string the model got (round 2 forced a line break here).
  { head: 'The retry line plus the exception text', who: 'The framework passes the exception on. The older OpenAI Agents SDK default.',
    text: `An error occurred while running the tool. Please try again. Error: 422 Unprocessable Entity: {"detail": [{"type": "enum", "loc": ["body", ⁅"priority"⁆], "msg": "Input should be ⁅'P0', 'P1' or 'P2'⁆", "input": "high", ...}]}`,
    trimmed: true,
    res: [['gpt-6-astra', 20], ['Qwen3.5 2B', 1]], why: 'Qwen3.5 2B filed 19 tickets as P0 (critical), with no error', warn: true },
  { head: 'A note that explains the codes and the next step', who: 'Your team writes it, in any framework.',
    text: `⁅priority⁆ is not valid. Allowed values: ⁅P0${NB}(critical)⁆, ⁅P1${NB}(high)⁆, ⁅P2${NB}(normal)⁆. Next step: call create_ticket again with priority set to one of these codes.`,
    res: [['gpt-6-astra', 20], ['Qwen3.5 2B', 20]], why: 'Both sent P1 on the second call' },
];
const OUT_HEAD = 'Runs that filed the ticket as P1 (high)';
const busX = M + 22, cardX = M + 70, cardW = WD - M - cardX;
const LW = cardW - 2 * PAD;                              // the text runs the full card width
const LT = 28, WHO = 26, WHO_LH = 34, OH = 26, RN = 40, WHY = 26, WHY_LH = 34, SP = 18;
const COL = [0, 530], NUM_END = 330;                     // results: two model columns, numbers right-aligned in each
const busArrows = [];
y += 40;
OPTS.forEach((o, i) => {
  const name = `card ${i + 1}`, strip = `results ${i + 1}`, cardY = y;
  const lb = cardY + PAD + LT * 0.76 + 2;
  if (f.width(o.head, LT, true) > cardW - 2 * PAD) notes.push(`card heading longer than one line: "${o.head}"`);
  const whoL = f.wrap(o.who, cardW - 2 * PAD, WHO);
  const whoB = lb + WHO_LH + 2;
  const headLast = whoB + (whoL.length - 1) * WHO_LH;
  const ruleY = headLast + WHO * 0.24 + 14;
  const monoB = ruleY + 18 + CODE * 0.76 + 2;
  // measure first, draw after the card box so the box sits under its text
  const nMono = monoLines(o.text, LW).length;
  const monoLast = monoB + (nMono - 1) * CODE_LH;
  const stripY = Math.round(monoLast + CODE * 0.24 + 22);
  const sx0 = cardX + PAD + SP, sW = cardW - 2 * PAD;
  const whyL = f.wrap(o.why, sW - 2 * SP, WHY, !!o.warn);
  const hb = stripY + SP + OH * 0.76 + 2;
  const rb = hb + 50;
  const wb = rb + 44;
  const stripH = Math.ceil(wb + (whyL.length - 1) * WHY_LH + WHY * 0.24 + SP + 2 - stripY);
  const cardH = Math.ceil(stripY + stripH + PAD - cardY);
  box(name, cardX, cardY, cardW, cardH, '#FFFFFF', P.INK3);
  T(cardX + PAD, lb, o.head, { size: LT, weight: 700, key: true }, name);
  whoL.forEach((s, j) => T(cardX + PAD, whoB + j * WHO_LH, s, { size: WHO, fill: GREY }, name));
  f.raw(`<line x1="${cardX + PAD}" y1="${ruleY}" x2="${cardX + cardW - PAD}" y2="${ruleY}" stroke="${P.RULE}" stroke-width="1.4"/>`);
  const { last, lastW } = mono(cardX + PAD, monoB, o.text, LW, name);
  if (Math.abs(last - monoLast) > 0.5) notes.push(`card text height drifted: ${name}`);
  if (o.trimmed) T(cardX + PAD + lastW + 16, last, '(trimmed)', { size: 24, fill: GREY }, name);
  box(strip, cardX + PAD, stripY, sW, stripH, P.BG, P.RULE, 1.2, name, 8);
  T(sx0, hb, OUT_HEAD, { size: OH, fill: GREY }, strip);
  o.res.forEach(([m, n], j) => {
    const cx = sx0 + COL[j];
    T(cx, rb, m, { size: 28, fill: P.INK2, key: true }, strip);
    T(cx + NUM_END, rb + 1, `${n} of 20`, { size: RN, weight: 700, fill: n === 20 ? P.GREEN : P.WARN_TEXT, anchor: 'end', key: true }, strip);
  });
  whyL.forEach((s, j) => T(sx0, wb + j * WHY_LH, s, { size: WHY, weight: o.warn ? 700 : 400, fill: o.warn ? P.WARN_TEXT : P.INK2 }, strip));
  busArrows.push([lb - LT * 0.36, name]);
  y = cardY + cardH + 24;
});
y -= 24;
// one line down the left edge from the band, then an arrow into each card
const busBot = busArrows[busArrows.length - 1][0];
f.raw(`<line x1="${busX}" y1="${bandY + bandH}" x2="${busX}" y2="${busBot}" stroke="${P.INK3}" stroke-width="2.2"/>`);
segs.push({ a: [busX, bandY + bandH], b: [busX, busBot], from: 'band', to: 'card 3' });
busArrows.forEach(([ay, name]) => arrow([[busX, ay], [cardX, ay]], 'band', name));

// ---- footer ----
y += 50;
// names the SDK the way run-results.png and the README do
// round 3: the version numbers moved here from the card headings, and "line" became "message" (cold read)
const FOOT = [
  'Source: the experiment in this repo, on OpenAI Agents SDK 0.24.0, 20 runs per model for each text.',
  'Each run had the SDK’s default limit of 10 turns. The older text came from the 0.22.3 error handler.',
  'gpt-6-astra is a hosted OpenAI model. Qwen3.5 2B is a small local model.',
  'The ticket service is made up for the test.',
];
FOOT.forEach(s => {
  if (f.width(s, 24) > WD - 2 * M) notes.push(`footer line longer than one line: "${s}"`);
  T(M, y, s, { size: 24, fill: GREY }); y += 32;
});

// ---- checks ----
const hit = (a, b, pad = 0) => a.x0 - pad < b.x1 && b.x0 < a.x1 + pad && a.y0 - pad < b.y1 && b.y0 < a.y1 + pad;
function check() {
  const out = [...new Set(notes)];
  for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
    const p = texts[i], q = texts[j];
    // two style runs on one baseline may touch end to end, but not overlap
    const abut = p.base === q.base && (Math.abs(p.x1 - q.x0) < 0.5 || Math.abs(q.x1 - p.x0) < 0.5);
    if (!abut && hit(p, q)) out.push(`text overlap: "${p.s}" / "${q.s}"`);
  }
  for (const t of texts) {
    const anc = t.host ? ancestors(t.host) : [];
    for (const r of rects) {
      if (t.host === r.name) {
        if (t.x0 < r.x0 + 12 || t.x1 > r.x1 - 12 || t.y0 < r.y0 + 8 || t.y1 > r.y1 - 8) out.push(`text not inside its ${r.name}: "${t.s}"`);
      } else if (anc.includes(r.name)) continue;          // inside a box that sits inside r
      else if (hit(t, r, 10)) out.push(`text touches ${r.name}: "${t.s}"`);
    }
    if (t.x0 < M - 1 || t.x1 > WD - M + 1) out.push(`text outside the margins: "${t.s}"`);
    for (const g of segs) {
      const sr = { x0: Math.min(g.a[0], g.b[0]), y0: Math.min(g.a[1], g.b[1]), x1: Math.max(g.a[0], g.b[0]), y1: Math.max(g.a[1], g.b[1]) };
      if (hit(t, sr, 8)) out.push(`text touches an arrow (${g.from} to ${g.to}): "${t.s}"`);
    }
  }
  // highlights: never over a neighbouring character, never left of the text column they sit in
  for (const m of marks) {
    if (m.x0 < m.col - 0.01) out.push(`highlight sticks out left of its text column: "${m.s}"`);
    for (const t of texts) {
      if (Math.abs(t.base - m.base) > 0.5 || (t.s === m.s && t.x0 >= m.x0 - 0.01 && t.x0 <= m.x0 + 2.01)) continue;
      if (Math.min(t.x1, m.x1) - Math.max(t.x0, m.x0) > 0.5) out.push(`highlight "${m.s}" covers part of "${t.s}"`);
    }
  }
  // outcome numbers must not crowd the model names
  for (const t of texts) for (const u of texts) if (t !== u && t.base + 1 === u.base && /of 20$/.test(u.s) && !/of 20$/.test(t.s) && t.x1 < u.x0 && u.x0 - t.x1 < 24) out.push(`number crowds its label: "${t.s}" / "${u.s}"`);
  // no dead zone: the content of each flow box and each results strip reaches near its foot
  for (const r of rects.filter(q => /^(call|reject|results \d)$/.test(q.name))) {
    const bot = Math.max(...texts.filter(t => t.host === r.name).map(t => t.y1));
    const slack = r.y1 - PAD - bot;
    if (slack > MAX_SLACK) out.push(`empty space at the foot of ${r.name}: ${Math.round(slack)} px`);
  }
  // each card: its text ends right above its results strip, so no card holds a hole
  for (const r of rects.filter(q => /^results \d$/.test(q.name))) {
    const mono = texts.filter(t => t.host === r.parent && t.y0 > rects.find(q => q.name === r.parent).y0 + 40);
    const gap = r.y0 - Math.max(...mono.map(t => t.y1));
    if (gap > MAX_SLACK) out.push(`gap above ${r.name}: ${Math.round(gap)} px`);
  }
  for (const g of segs) {
    if (g.a[0] !== g.b[0] && g.a[1] !== g.b[1]) out.push(`diagonal arrow ${g.from} to ${g.to}`);
    const sr = { x0: Math.min(g.a[0], g.b[0]), y0: Math.min(g.a[1], g.b[1]), x1: Math.max(g.a[0], g.b[0]), y1: Math.max(g.a[1], g.b[1]) };
    for (const r of rects) if (r.name !== g.from && r.name !== g.to && hit(sr, r, -1)) out.push(`arrow ${g.from} to ${g.to} crosses ${r.name}`);
    const len = Math.hypot(g.b[0] - g.a[0], g.b[1] - g.a[1]);
    if (len < 36) out.push(`arrow ${g.from} to ${g.to} too short (${len})`);
  }
  for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
    const a = rects[i], b = rects[j];
    if (a.parent === b.name || b.parent === a.name) {
      const [p, c] = b.parent === a.name ? [a, b] : [b, a];
      if (c.x0 < p.x0 + 8 || c.x1 > p.x1 - 8 || c.y0 < p.y0 + 8 || c.y1 > p.y1 - 8) out.push(`${c.name} not inside ${p.name}`);
    } else if (a.parent && a.parent === b.parent) {
      if (hit(a, b, 4)) out.push(`boxes touch: ${a.name} / ${b.name}`);
    } else if (hit(a, b, 20)) out.push(`boxes closer than 20 px: ${a.name} / ${b.name}`);
  }
  return out;
}

(async () => {
  const problems = check();
  const warn = await f.render('hero-what-the-model-read', [], process.env.OUT || undefined, { gap: 0 });
  const all = [...problems, ...warn];
  const flowSlack = rects.filter(q => /^(call|reject)$/.test(q.name))
    .map(r => `${r.name} ${Math.round(r.y1 - PAD - Math.max(...texts.filter(t => t.host === r.name).map(t => t.y1)))}`);
  console.log('card text width', Math.round(LW), '| setup content', Math.round(scW), '| flow foot slack', flowSlack.join(', '));
  if (all.length) { console.log('GEOMETRY:\n  ' + all.join('\n  ')); process.exitCode = 1; }
  else console.log('geometry clean:', texts.length, 'texts,', rects.length, 'boxes,', segs.length, 'arrow segments');
})();
