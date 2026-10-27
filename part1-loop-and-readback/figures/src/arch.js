// Shared drawing helpers for the series figures (architecture diagrams and decision charts).
// Cloth ground #F4F1EA, Helvetica, phone-size text (a 1400-wide figure shows at about 0.27x on a phone, so body
// text is 22 or more). Text wraps by measured Helvetica widths (helv_widths.json, from PIL at size 100), so a
// label can never run past its box. Render: SVG at 2x through sharp (pinned in ../package.json).
// The SVG names Helvetica and Menlo, so the PNG matches the committed one only where those fonts are installed
// (macOS has both). Elsewhere the renderer falls back to another font and text widths drift.
// Usage in a figure file:
//   const A = require('./arch'); const f = A.fig(1400);
//   f.header('EYEBROW', ['Headline line'], ['Subhead line']);
//   const b = f.box(60, 300, 260, 120, { kind: 'service', title: 'Ticket service', lines: ['accepts P0, P1 or P2'] });
//   f.arrow([[b.r, b.cy], [500, b.cy]], { label: 'create_ticket' });
//   await f.render('name', 'footer text');   // writes ../name.png and returns warnings
const sharp = require('sharp');
const path = require('path');
const W = require('./helv_widths.json');

const P = {
  BG: '#F4F1EA', INK: '#14120E', INK2: '#4A463D', INK3: '#6B665C', RULE: '#C9C4B8',
  COOL: '#2E6FB8', COOL_FILL: '#EEF4FB', GOLD: '#C9922B', GOLD_TEXT: '#7A5A12', GOLD_FILL: '#FBF3E3',
  WELL: '#EAE4D6', EXT: '#8A8172', WARN: '#B4432B', WARN_TEXT: '#8E3220', WARN_FILL: '#FBEDEA',
  GREEN: '#2E7D46', GREEN_FILL: '#EAF4EC',
};
// box kinds: service = a model, a service or a tool, person = a human, ext = an outside or legacy system,
// store = data, control = security or policy, note = an amber side note, ops = logging and monitoring,
// good / bad = an outcome
const KIND = {
  service: { fill: P.COOL_FILL, stroke: P.COOL, title: P.INK },
  person: { fill: P.GOLD_FILL, stroke: P.GOLD, title: P.INK },
  ext: { fill: P.WELL, stroke: P.EXT, title: P.INK },
  store: { fill: P.WELL, stroke: P.INK3, title: P.INK },
  control: { fill: '#FFFFFF', stroke: P.GOLD, title: P.GOLD_TEXT },
  note: { fill: P.GOLD_FILL, stroke: P.GOLD, title: P.GOLD_TEXT },
  ops: { fill: P.WELL, stroke: P.INK3, title: P.INK },
  good: { fill: P.GREEN_FILL, stroke: P.GREEN, title: P.GREEN },
  bad: { fill: P.WARN_FILL, stroke: P.WARN, title: P.WARN_TEXT },
  plain: { fill: '#FFFFFF', stroke: P.INK3, title: P.INK },
};
const SANS = 'Helvetica, Arial, sans-serif';
const MONO = 'Menlo, monospace';
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function width(s, size, bold = false) {
  const t = W[bold ? 'b' : 'r'];
  let w = 0;
  for (const c of String(s)) w += (t[c] != null ? t[c] : t['M'] * 0.6);
  return (w * size) / 100;
}
// monospace width (Menlo is about 0.602 em per glyph)
const monoWidth = (s, size) => String(s).length * size * 0.602;
function wrap(s, maxW, size, bold = false) {
  const words = String(s).split(' ');
  const out = []; let cur = '';
  for (const w of words) {
    const t = cur ? cur + ' ' + w : w;
    if (width(t, size, bold) <= maxW || !cur) cur = t; else { out.push(cur); cur = w; }
  }
  if (cur) out.push(cur);
  return out;
}

function fig(Wd = 1400, opts = {}) {
  const parts = []; const warn = []; let bottom = 0;
  const track = y => { if (y > bottom) bottom = y; };
  const text = (x, y, s, o = {}) => {
    const { size = 22, weight = 400, fill = P.INK, anchor = 'start', family = SANS, spacing = 0, halo = false } = o;
    const h = halo ? ` stroke="${P.BG}" stroke-width="6" stroke-linejoin="round" paint-order="stroke"` : '';
    parts.push(`<text x="${x}" y="${y}" font-family="${family}" font-size="${size}" font-weight="${weight}" fill="${fill}" `
      + `text-anchor="${anchor}" letter-spacing="${spacing}"${h}>${esc(s)}</text>`);
    const w = family === MONO ? monoWidth(s, size) : width(s, size, weight >= 600);
    const x0 = anchor === 'middle' ? x - w / 2 : anchor === 'end' ? x - w : x;
    if (x0 < 20 || x0 + w > Wd - 20) warn.push(`text off the edge: "${s}"`);
    track(y + size * 0.3);
    return w;
  };
  const f = {
    P, W: Wd, warn, text, width, wrap,
    // eyebrow, rule, headline lines, subhead lines. Returns the y below the header.
    header(eyebrow, heads, subs = []) {
      text(60, 56, eyebrow, { size: 22, family: MONO, fill: P.GOLD_TEXT, spacing: 3 });
      parts.push(`<line x1="60" y1="76" x2="${Wd - 60}" y2="76" stroke="${P.GOLD}" stroke-width="2"/>`);
      let y = 128;
      heads.forEach((s, i) => { text(60, y, s, { size: 40, weight: 700 }); if (i < heads.length - 1) y += 48; });
      y += 46;
      subs.forEach((s, i) => { text(60, y, s, { size: 28, fill: P.INK2 }); if (i < subs.length - 1) y += 36; });
      return y + 50;
    },
    // A box with a bold title and wrapped lines, centred. kind from KIND. Returns geometry for arrows.
    box(x, y, w, h, o = {}) {
      const { kind = 'service', title = '', lines = [], titleSize = 24, size = 21, dashed = false, r = 10, mono = false } = o;
      const k = KIND[kind];
      parts.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${k.fill}" stroke="${k.stroke}" `
        + `stroke-width="${kind === 'control' || kind === 'note' ? 2.2 : 1.8}"${dashed ? ' stroke-dasharray="7 5"' : ''}/>`);
      const pad = 16, maxW = w - 2 * pad;
      const tl = title ? wrap(title, maxW, titleSize, true) : [];
      const bl = []; lines.forEach(s => bl.push(...wrap(s, maxW, size)));
      const lhT = titleSize * 1.22, lhB = size * 1.3;
      const total = tl.length * lhT + (tl.length && bl.length ? 6 : 0) + bl.length * lhB;
      if (total > h - 12) warn.push(`box too short for its text: "${title || lines[0]}" needs ${Math.ceil(total + 16)}, has ${h}`);
      let ty = y + (h - total) / 2 + titleSize * 0.85;
      tl.forEach(s => { text(x + w / 2, ty, s, { size: titleSize, weight: 700, fill: k.title, anchor: 'middle' }); ty += lhT; });
      if (tl.length) ty = y + (h - total) / 2 + tl.length * lhT + 6 + size * 0.85;
      bl.forEach(s => { text(x + w / 2, ty, s, { size, fill: P.INK2, anchor: 'middle', family: mono ? MONO : SANS }); ty += lhB; });
      track(y + h);
      return { x, y, w, h, l: x, r: x + w, t: y, b: y + h, cx: x + w / 2, cy: y + h / 2 };
    },
    // A labelled frame around a group of boxes (drawn first, under them).
    group(x, y, w, h, label, o = {}) {
      const { stroke = P.RULE, fill = 'none', dashed = true } = o;
      parts.unshift(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="14" fill="${fill}" stroke="${stroke}" stroke-width="1.6"${dashed ? ' stroke-dasharray="8 6"' : ''}/>`
        + `<text x="${x + 18}" y="${y + 30}" font-family="${SANS}" font-size="22" font-weight="700" fill="${P.INK3}">${esc(label)}</text>`);
      track(y + h);
      return { x, y, w, h, l: x, r: x + w, t: y, b: y + h, cx: x + w / 2, cy: y + h / 2 };
    },
    // A decision diamond with wrapped text.
    diamond(cx, cy, w, h, s, o = {}) {
      const { size = 21 } = o;
      parts.push(`<polygon points="${cx},${cy - h / 2} ${cx + w / 2},${cy} ${cx},${cy + h / 2} ${cx - w / 2},${cy}" fill="#FFFFFF" stroke="${P.COOL}" stroke-width="2"/>`);
      const ls = wrap(s, w * 0.62, size, true);
      const lh = size * 1.25; let y = cy - ((ls.length - 1) * lh) / 2 + size * 0.35;
      if (ls.length * lh > h * 0.62) warn.push(`diamond too small for: "${s}"`);
      ls.forEach(t => { text(cx, y, t, { size, weight: 700, anchor: 'middle' }); y += lh; });
      track(cy + h / 2);
      return { l: cx - w / 2, r: cx + w / 2, t: cy - h / 2, b: cy + h / 2, cx, cy };
    },
    // An orthogonal or straight arrow through the given points, head at the last point.
    // o.label sits on the longest segment with a white halo. o.both adds a head at the start.
    arrow(pts, o = {}) {
      const { label = '', dashed = false, color = P.INK3, both = false, size = 20, lw = 2, labelAt = null, labelDy = -8 } = o;
      const head = (a, b) => {
        const [x1, y1] = a, [x2, y2] = b; const ang = Math.atan2(y2 - y1, x2 - x1); const L = 12, Wh = 6.5;
        const bx = x2 - L * Math.cos(ang), by = y2 - L * Math.sin(ang);
        return `<polygon points="${x2},${y2} ${(bx + Wh * Math.sin(ang)).toFixed(1)},${(by - Wh * Math.cos(ang)).toFixed(1)} ${(bx - Wh * Math.sin(ang)).toFixed(1)},${(by + Wh * Math.cos(ang)).toFixed(1)}" fill="${color}"/>`;
      };
      const short = (a, b, d) => { const ang = Math.atan2(b[1] - a[1], b[0] - a[0]); return [b[0] - d * Math.cos(ang), b[1] - d * Math.sin(ang)]; };
      const q = pts.map(p => p.slice());
      q[q.length - 1] = short(q[q.length - 2], q[q.length - 1], 10);
      if (both) q[0] = short(q[1], q[0], 10);
      parts.push(`<polyline points="${q.map(p => p.join(',')).join(' ')}" fill="none" stroke="${color}" stroke-width="${lw}"${dashed ? ' stroke-dasharray="8 6"' : ''} stroke-linejoin="round"/>`
        + head(pts[pts.length - 2], pts[pts.length - 1]) + (both ? head(pts[1], pts[0]) : ''));
      if (label) {
        let best = 0, bi = 0;
        for (let i = 0; i < pts.length - 1; i++) { const d = Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]); if (d > best) { best = d; bi = i; } }
        const [a, b] = [pts[bi], pts[bi + 1]];
        const [lx, ly] = labelAt || [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        const vertical = Math.abs(b[0] - a[0]) < 1;
        if (!vertical && !labelAt && width(label, size) > best - 20) warn.push(`arrow label longer than its arrow: "${label}" (${Math.round(width(label, size))} vs ${Math.round(best)})`);
        text(vertical ? lx + 10 : lx, vertical ? ly + size * 0.35 : ly + labelDy, label,
          { size, fill: P.INK2, anchor: vertical ? 'start' : 'middle', halo: true });
      }
    },
    raw(s) { parts.push(s); },
    // Footer lines in grey under everything drawn so far, then render. Returns the warnings.
    async render(name, footerLines = [], outDir = path.join(__dirname, '..'), ro = {}) {
      // local extension: ro.fx = footer x, ro.gap = space above the footer
      const fx = ro.fx != null ? ro.fx : 60, gap = ro.gap != null ? ro.gap : 60;
      let y = bottom + gap;
      const fl = []; footerLines.forEach(s => fl.push(...wrap(s, Wd - 2 * fx, 22)));
      fl.forEach((s, i) => { text(fx, y + i * 30, s, { size: 22, fill: P.INK3 }); });
      const H = Math.ceil((fl.length ? y + (fl.length - 1) * 30 : bottom) + 40);
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${Wd * 2}" height="${H * 2}" viewBox="0 0 ${Wd} ${H}">`
        + `<rect width="${Wd}" height="${H}" fill="${P.BG}"/>${parts.join('')}</svg>`;
      const out = path.join(outDir, `${name}.png`);
      if (process.env.DUMP) require('fs').writeFileSync(path.join(process.env.DUMP, `${name}.svg`), svg);
      await sharp(Buffer.from(svg)).png().toFile(out);
      console.log(`${name}.png ${Wd * 2}x${H * 2}`, warn.length ? `WARNINGS:\n  ${warn.join('\n  ')}` : 'no warnings');
      return warn;
    },
  };
  return f;
}
module.exports = { fig, P, width, wrap, KIND };
