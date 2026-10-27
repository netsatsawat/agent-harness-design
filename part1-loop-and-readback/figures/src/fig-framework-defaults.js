// What eight agent frameworks do, with every default left alone, when the ticket tool from the opening raises on a
// 422 from the ticket service. One row per framework, in three groups by what the model reads next: nothing (the run
// stops), the raw exception, or a fixed line. Each row names how a team sets what the model reads, and the loop limit
// that ships on, with the setting that changes it written as it is typed. It answers whether Part 1 applies to
// LangGraph, Strands and the other frameworks.
// Facts come from ../../framework-defaults/: the check scripts and outputs in each framework's folder, and the
// per-framework summary in its README.md. The build reads them and fails if any version, hook name, limit number,
// setting, footnote or quoted error text is no longer backed, so the figure and the checks cannot drift apart. A quoted
// error line may be cut with "...", but every piece must sit, in order, on one line of that framework's output.
// RESEARCH=<folder> also checks each cell against the research notes the checks came from (VERIFIED.md under
// <folder>/framework-defaults/ and the OpenAI defaults JSON in <folder>), the way the article build does. Those notes
// are not in this repo, so without RESEARCH that part of the check is skipped.
// Layout follows fig-design-review.js: 1200 wide, eyebrow, gold rule, bold title, dek, card rows, no text under 28 px,
// except setting names and footer code in small Menlo at 26 (Menlo's x-height at 26 matches Helvetica at 28).
// Group colours carry meaning: red where the run stops, amber where the model reads the raw exception, grey where a
// fixed line hides it. Code identifiers are in Menlo.
// Round 2 (2026-10-27, after a cold read of round 1): version lines and footer one grey step darker and about 15
// percent larger (28 to 32, 24 to 28) so they read at 400 px. Quoted lines sit under their label so the longest one
// (OpenAI's) fits on one line at 28 px.
// Round 3 (2026-10-27, after the round 2 cold read and QA): the column headings repeat in every card, so they stay
// on screen on a phone. 'Write your own note with' became 'Set what the model reads' ('note' was never defined).
// Each row ends with a full-width line that gives the limit setting as it is typed, in body ink, because the bare
// names hid where the setting goes (request_limit only works inside UsageLimits, recursion_limit goes in the run
// config). Pydantic AI says why ToolFailed and not ModelRetry (check_repeat_failure.py: ModelRetry ends the run at the
// second failure). The two 'No limit' rows say what happens instead.
// Round 4 (2026-10-27, after the round 3 cold read and QA): the LangGraph row was named for both libraries but its fix
// only fits create_agent. It now has a bold header and two entry points, each on its own line of cells:
// create_agent (ToolErrorMiddleware, 9,999 steps) and ToolNode graphs or create_react_agent (handle_tool_errors,
// 10,007 steps). Both are configured defaults, so the numbers differ on purpose. The footer lines about ToolNode are
// gone. 'about 2 per model call' became its own line with its unit. Pydantic AI names the setting that moves its
// ModelRetry stop, Agent(retries=N). Microsoft and CrewAI name their earlier stops too (3 failed rounds in a row, the
// 5th identical call), so all three rows that stop early say so. Every setting shows the keyword it goes in
// (run_config=, usage_limits=, options=). Grey text is one more step darker for 400 px. Cards are 8 px wider each
// side, so the longest setting line (Microsoft's) keeps a margin.
// Run: node fig-framework-defaults.js   (OUT=<dir> writes the PNG elsewhere, DUMP=<dir> also writes the SVG)
const fs = require('fs');
const path = require('path');
const A = require('./arch');
const WD = 1200;
const f = A.fig(WD);
const { P } = f;
const MONO = 'Menlo, monospace';
const GREY = '#3A362F', GOLD_INK = '#654A0D';    // grey text, one step darker than P.INK2 (#4A463D) since round 4
const KEY_AT_400 = 9.3;                          // px on a 400 px phone: title, group titles, framework names

// ---- content ----
// a line is a list of runs, drawn with one space between runs: m = Menlo (code), s = Helvetica, t = Helvetica with no
// space before it (punctuation after code)
const m = s => ({ s, mono: true }), s = t => ({ s: t, mono: false }), t = x => ({ s: x, mono: false, tight: true });
const GROUPS = [
  { key: 'stop', title: 'The run stops',
    sub: ['Your code gets the exception, and the model reads nothing.',
      'Set what the model reads and the run goes on, up to the loop limit.'],
    stroke: P.WARN, band: P.WARN_FILL, ink: P.WARN_TEXT },
  { key: 'raw', title: 'The model reads the raw exception',
    sub: ['The text includes the server’s 422 body, which lists the allowed codes.'],
    ex: [{ from: 'CrewAI', fid: 'F1_error_readback', text: "Error executing tool: 422 ... 'P0', 'P1' or 'P2' ..." }],
    stroke: P.GOLD, band: P.GOLD_FILL, ink: GOLD_INK },
  { key: 'fixed', title: 'The model reads a fixed line',
    sub: ['The line hides the exception and the 422 body.'],
    ex: [{ from: 'OpenAI', text: 'An error occurred while running the tool. Please try again.' },
      { from: 'Microsoft', fid: 'F1_error_readback', text: 'Error: Function failed.' }],
    stroke: P.INK3, band: P.WELL, ink: P.INK2 },
];
const HEADS = ['Framework', 'Set what the model reads', 'Loop limit by default'];
const LIMIT = s('Set the limit with');
// A row is one framework. label = its name in messages and example labels.
// parts = its lines of cells, one per entry point. A part has name and ver (lines of runs), note (lines of runs; lines
// from noteDim on are a side remark in grey) and lim (blocks of lines: the first line of each block in ink, the rest
// grey). head = a bold line across the row, above its parts, when a framework has more than one entry point; the part
// names are then the entry points.
// knobs = the setting lines at the row's foot, as typed (Menlo runs are code). tail = grey lines under them.
// src = the heading prefix of the framework's section in VERIFIED.md, or 'openai' for the JSON file (RESEARCH only).
// readme = the heading prefix of the framework's section in ../../framework-defaults/README.md.
// dir = the framework's folder under framework-defaults/: its check scripts and outputs back the code identifiers,
// and its output files back the version.
// ev = strings that must appear in the VERIFIED.md section (RESEARCH only).
// xev = [source, string] pairs that are always checked ('file:<path>' = a file under framework-defaults/). They back
// each row's group and limit numbers with the check outputs.
// calc = a number in the grey line under the settings, worked out from a check output (LangGraph's steps per call).
const one = (name, ver, note, lim, o = {}) => [{ name, ver, note, lim, ...o }];
const ROWS = [
  { g: 'stop', label: 'LangGraph and LangChain', head: 'LangGraph and LangChain',
    parts: [
      { name: [[m('create_agent')]], ver: [[s('langchain 1.4.7')]],
        note: [[m('ToolErrorMiddleware')], [s('in'), m('middleware=[...]')]], lim: [['9,999 steps', 'then an exception']] },
      { name: [[m('ToolNode'), s('graphs or')], [m('create_react_agent')]], ver: [[s('langgraph 1.2.18')]],
        note: [[m('handle_tool_errors')], [s('on'), m('ToolNode')]], lim: [['10,007 steps', 'then an exception']] },
    ],
    knobs: [[LIMIT, m('config={"recursion_limit": N}')]], tail: ['One model call is about 2 steps'],
    src: 'LangGraph', readme: 'LangGraph', dir: 'langgraph',
    ev: ['langgraph 1.2.18', 'langchain 1.4.7', 'stops the run', 'create_agent and create_react_agent behave the same way',
      'On create_agent, a team swaps in its own note with ToolErrorMiddleware',
      'On a bare ToolNode (also passed to create_react_agent), the knob is ToolNode(handle_tool_errors=...)',
      'create_agent pins 9_999', "Plain graphs and create_react_agent use langgraph 1.2.18's default of 10_007",
      'each model call and each tools run is one step', 'create_agent after 5,000 model calls',
      'raise GraphRecursionError to the caller',
      'You can increase the limit by setting the `recursion_limit` config key'],
    // ToolErrorMiddleware only wraps the tool call, so it adds no graph step: still 2 steps per model call.
    // The ToolNode line: a hand-built StateGraph with ToolNode, defaults untouched (check_langgraph_toolnode_graph.py)
    xev: [['file:langgraph/output-toolnode-graph.txt', 'DEFAULTS UNTOUCHED: hand-built StateGraph + ToolNode(tools)'],
      ['file:langgraph/output-toolnode-graph.txt', 'exception type: __main__.ServerValidationError'],
      ['file:langgraph/output-toolnode-graph.txt', 'turn 2: NEVER HAPPENED'],
      ['file:langgraph/output-toolnode-graph.txt', 'Recursion limit of 10007 reached'],
      ['file:langgraph/output-toolnode-graph.txt', 'model calls made: 5004   ping executions: 5003'],
      ['file:langgraph/output-toolnode-graph.txt', 'NON-DEFAULT recursion_limit=50'],
      ['file:langgraph/output-toolnode-graph.txt', 'model calls made: 25   ping executions: 25'],
      ['file:langgraph/check_langgraph_defaults.py', 'middleware=[ToolErrorMiddleware(on_error=team_note)]'],
      ['file:langgraph/output.txt', 'turn 2: NEVER HAPPENED (the model was not called again)'],
      ['file:langgraph/output-full-default-loop.txt', 'Recursion limit of 9999 reached'],
      ['file:langgraph/output-full-default-loop.txt', 'model calls made: 5000   ping executions: 4999']],
    // steps per model call: the recursion limit over the model calls it allowed, in the ToolNode graph run
    calc: { file: 'langgraph/output-toolnode-graph.txt',
      re: /NON-DEFAULT recursion_limit=(\d+)\n[^=]*?model calls made: (\d+)/, fn: (lim, calls) => lim / calls } },
  { g: 'stop', label: 'Google ADK',
    parts: one([[s('Google ADK')]], [[s('2.13.0')]], [[m('on_tool_error_callback')]], [['500 model calls', 'then an exception']]),
    knobs: [[LIMIT, m('run_config=RunConfig(max_llm_calls=N)')]], src: 'Google Agent Development Kit',
    readme: 'Google Agent Development Kit', dir: 'google-adk',
    ev: ['Version: 2.13.0', 'stops the run', 'on_tool_error_callback', 'RunConfig.max_llm_calls defaults to 500',
      'raises LlmCallsLimitExceededError to the caller'],
    xev: [['file:google-adk/check_adk_defaults.py', 'kwargs["run_config"] = run_config'],
      ['file:google-adk/output.txt', 'turn 2 never happened: the model received nothing after the failure'],
      ['file:google-adk/output.txt', 'Max number of llm calls limit of `500` exceeded']] },
  // ToolFailed, not ModelRetry: ModelRetry spends the tool's retry budget (default 1), so the second failure ends the
  // run, while ToolFailed spends none and the run goes on to request_limit (check_repeat_failure.py, R1 and R2).
  // Agent(retries=N) sets that budget for every tool (an int sets the tools and output budgets, agent/__init__.py at
  // tag v2.61.0); @agent.tool(retries=N) sets it for one tool.
  { g: 'stop', label: 'Pydantic AI',
    parts: one([[s('Pydantic AI')]], [[s('2.61.0')]],
      [[s('raise'), m('ToolFailed')], [m('ModelRetry'), s('ends the run')], [s('at the second failure')]],
      [['50 model requests', 'then an exception']], { noteDim: 1 }),
    knobs: [[LIMIT, m('usage_limits=UsageLimits(request_limit=N)')],
      [s('Set the retries for'), m('ModelRetry'), s('with'), m('Agent(retries=N)')]],
    src: 'Pydantic AI', readme: 'Pydantic AI', dir: 'pydantic-ai',
    ev: ['Version: 2.61.0', 'ends the run', "ToolFailed(text), which gives outcome 'failed' and uses no budget",
      "ModelRetry(text), which gives outcome 'retried' and uses the tool's retry budget",
      'The default budget is 1 retry per tool (Agent retries default 1',
      'The next failure of the same tool raises UnexpectedModelBehavior',
      'UsageLimits.request_limit=50', 'applied by default when usage_limits is not passed',
      'the run raises UsageLimitExceeded'],
    xev: [['file:pydantic-ai/output-repeat-failure.txt', 'ToolFailed importable from pydantic_ai'],
      ['file:pydantic-ai/output-repeat-failure.txt', 'pydantic_ai.exceptions.UnexpectedModelBehavior'],
      ['file:pydantic-ai/output-repeat-failure.txt', 'model calls made: 2   tool executions: 2'],
      ['file:pydantic-ai/output-repeat-failure.txt', 'model calls made: 50   tool executions: 50'],
      ['file:pydantic-ai/output.txt', '"exception_type": "__main__.ServerValidationError"'],
      ['file:pydantic-ai/output.txt', '"request_limit": 50']] },
  { g: 'raw', label: 'Strands Agents',
    parts: one([[s('Strands Agents')]], [[s('1.62.0')]], [[m('AfterToolCallEvent'), s('hook')]],
      [['No limit, runs until', 'a Python recursion error']]),
    knobs: [[LIMIT, m('agent(prompt, limits={"turns": N})')]], src: 'Strands Agents', readme: 'Strands Agents',
    dir: 'strands',
    ev: ['Version: 1.62.0', 'does not stop the run', 'the whole 422 body', 'AfterToolCallEvent hook',
      'has no default turn limit', "runs until Python's recursion limit raises EventLoopException (cause RecursionError)",
      'agent(prompt, limits={"turns": N})'],
    xev: [['file:strands/output.txt', 'turn 2: text verbatim -> Error: ServerValidationError - 422 Unprocessable Entity'],
      ['file:strands/output.txt', '__cause__: RecursionError: maximum recursion depth exceeded']] },
  // the 5th identical call (same tool, args and result) raises ToolExecutionFailedError (crewai/output.txt scenario 8)
  { g: 'raw', label: 'CrewAI',
    parts: one([[s('CrewAI')]], [[s('1.15.30')]], [[m('after_tool_call'), s('hook')]],
      [['25 iterations', 'then a forced final answer'], ['The 5th identical call', 'raises an exception']]),
    knobs: [[LIMIT, m('Agent(max_iter=N)')]], src: 'CrewAI', readme: 'CrewAI', dir: 'crewai',
    ev: ['Version: 1.15.30', 'does not stop the run', 'The full 422 body reaches the model',
      'after_tool_call hook', 'Agent.max_iter defaults to 25', 'a user message demanding a final answer',
      "that reply becomes the run's normal output",
      'the 5th identical call (same tool, args and result) raises ToolExecutionFailedError to the caller'],
    xev: [['file:crewai/output.txt', "called 'create_ticket' with the same arguments 5 times"],
      ['file:crewai/output.txt', 'agent.max_iter=25'],
      ['file:crewai/output.txt', "Now it's time you MUST give your absolute best final answer."]] },
  { g: 'raw', label: 'Claude Agent SDK',
    parts: one([[s('Claude Agent SDK*')]], [[s('0.2.174')]], [[s('return'), m('is_error')], [s('from the tool')]],
      [['No limit, runs while', 'the model calls tools']]),
    knobs: [[LIMIT, m('options=ClaudeAgentOptions(max_turns=N)')]], src: 'Claude Agent SDK',
    readme: 'Claude Agent SDK', dir: 'claude-agent-sdk',
    ev: ['Version: 0.2.174', 'does not stop the run', 'str(exception) as the only text',
      '"is_error": True} yourself', 'max_turns defaults to None',
      'Only when that is unset too does the loop run until the model stops calling tools'],
    xev: [['file:claude-agent-sdk/check_claude_agent_sdk_defaults.py', 'options=ClaudeAgentOptions(max_turns=3)'],
      ['file:claude-agent-sdk/output.txt', 'text == str(exception): True'],
      ['file:claude-agent-sdk/output.txt', 'ClaudeAgentOptions().max_turns = None'],
      ['file:claude-agent-sdk/output.txt', 'defaults (+ mcp_servers only) : limit/approval flags passed to the CLI = none']] },
  { g: 'fixed', label: 'OpenAI Agents SDK',
    parts: one([[s('OpenAI Agents SDK')]], [[s('0.24.0')]], [[m('tool_error_formatter')]], [['10 turns', 'then an exception']]),
    knobs: [[LIMIT, m('Runner.run(agent, input, max_turns=N)')]], src: 'openai', readme: 'OpenAI Agents SDK',
    dir: 'openai-agents',
    ev: ['openai-agents 0.24.0 (latest on PyPI', 'returns one fixed line', 'It no longer passes the exception text',
      'RunConfig.tool_error_formatter', 'DEFAULT_MAX_TURNS is 10', 'raises MaxTurnsExceeded', 'Runner.run, run_sync and run_streamed all default max_turns='],
    // the line the model reads at 0.24.0 has no error text after it (0.22.3 added 'Error: ...'; D1-change)
    xev: [['file:openai-agents/output.txt', 'openai-agents==0.24.0'],
      ['file:openai-agents/output.txt', '"output": "An error occurred while running the tool. Please try again.", "type": "function_call_output"'],
      ['file:openai-agents/output.txt', 'DEFAULT_MAX_TURNS = 10'],
      ['file:openai-agents/output.txt', 'exception str : Max turns (10) exceeded']] },
  // with the default fixed line, 3 failed rounds in a row turn tools off and force the answer after 4 model calls
  // (ms-agent-framework/output.txt scenario 5), long before the 40-round limit
  { g: 'fixed', label: 'Microsoft Agent Framework',
    parts: one([[s('Microsoft Agent')], [s('Framework')]], [[s('1.23.0')]], [[s('function middleware')]],
      [['40 rounds', 'then a forced final answer'], ['3 failed rounds in a row', 'force the answer sooner']]),
    knobs: [[LIMIT, m('function_invocation_configuration={"max_iterations": N}')]],
    src: 'Microsoft Agent Framework', readme: 'Microsoft Agent Framework', dir: 'ms-agent-framework',
    ev: ['Version: 1.23.0', 'does not stop the run', 'does not reach the result text',
      'write a function middleware', 'max_iterations=40', 'one more model call with tool_choice="none"',
      'returns that reply as the final answer', "the client's function_invocation_configuration",
      'after 3 such rounds in a row (max_consecutive_errors_per_request=3) it turns tools off and makes one last model call for a text answer'],
    xev: [['file:ms-agent-framework/output.txt', 'Maximum consecutive function call errors reached (3)'],
      ['file:ms-agent-framework/output.txt', 'last request: tool_choice = none | tool results the model has seen: 3'],
      ['file:ms-agent-framework/output.txt', "'max_iterations': 40"]] },
];
// footer: each line stays on one line. gap = extra space above the line, between footnotes. ev = [source, string]
// pairs that back it in the research notes (RESEARCH only), rev = pairs that back it in this repo ('readme' = the
// whole framework-defaults/README.md).
const FOOT = [
  { runs: [s('All eight are on their latest release as of Oct 27, 2026, with defaults left alone.')],
    ev: [['', '# Framework defaults, verified 2026-10-27']],
    rev: [['readme', 'was the latest stable release on PyPI on 2026-10-27']] },
  { runs: [s('The checks use a scripted stand-in model.')], ev: [['', 'a scripted stand-in model']],
    rev: [['readme', 'scripted stand-in model']] },
  { gap: 12, runs: [s('*By default the Claude Agent SDK denies a custom tool call that nobody approved.')],
    ev: [['Claude Agent SDK', 'denies the MCP call before the handler runs']],
    rev: [['file:claude-agent-sdk/output.txt', 'so it would deny this MCP call before the handler runs']] },
  { runs: [s('The check approved the tool so the call could run.')],
    ev: [['Claude Agent SDK', 'This only happens once the call is allowed']],
    rev: [['file:claude-agent-sdk/output.txt', 'This section shows what the model reads once the call is allowed to run.']] },
  { gap: 12, runs: [s('Source: the check scripts in framework-defaults/ in this repo.')] },
];

// ---- geometry trace ----
const boxes = []; const conts = {}; const cards = []; const notes = []; const dashes = [];
function T(x, y, str, o = {}, inside = null) {
  if (/[–—;]/.test(str)) notes.push(`dash or semicolon in figure text: "${str}"`);
  if (/\bI ran\b|\bjob\b|\bbill\b|\bblame|\bnote\b|schematic|\b(table|figure|fig\.) \d/i.test(str)) notes.push(`banned word in figure text: "${str}"`);
  const size = o.size || 28, min = o.small ? 26 : o.foot ? 24 : 28;
  if (size < min) notes.push(`text below ${min} px: "${str}"`);
  if (o.small && o.family !== MONO) notes.push(`small text that is not code: "${str}"`);
  if (o.key && size * 400 / WD < KEY_AT_400) notes.push(`key text below ${KEY_AT_400} px at 400 px wide: "${str}"`);
  const w = f.text(x, y, str, { ...o, size }) + (o.spacing || 0) * [...str].length;
  const anchor = o.anchor || 'start';
  const x0 = anchor === 'middle' ? x - w / 2 : anchor === 'end' ? x - w : x;
  boxes.push({ s: str, x0, y0: y - size * 0.76, x1: x0 + w, y1: y + size * 0.24, in: inside, base: y, tight: !!o.tight });
  return w;
}
const cont = (name, x0, y0, x1, y1) => (conts[name] = { x0, y0, x1, y1 });
// o.monoSize: Menlo runs drawn smaller than the Helvetica around them (footer and setting lines)
const runSize = (r, o) => (r.mono && o.monoSize ? o.monoSize : o.size);
const runW = (r, o) => (r.mono ? r.s.length * runSize(r, o) * 0.602 : f.width(r.s, o.size, (o.weight || 400) >= 600));
const SPACE = sz => f.width(' ', sz);
const lineW = (runs, o) => runs.reduce((a, r, i) => a + runW(r, o) + (i && !r.tight ? SPACE(o.size) : 0), 0);
function runs(x, y, line, o, inside) {
  let cx = x;
  line.forEach((r, i) => {
    if (i && !r.tight) cx += SPACE(o.size);
    const ro = r.mono ? { family: MONO, size: runSize(r, o), ...(o.monoSize ? { small: true } : {}), ...(o.monoFill ? { fill: o.monoFill } : {}) } : {};
    cx += T(cx, y, r.s, { ...o, ...ro, tight: r.tight }, inside);
  });
  return cx - x;
}

// ---- the facts check: every cell must be backed by the checks in framework-defaults/ ----
const FD = path.join(__dirname, '..', '..', 'framework-defaults');
// optional: the research notes the checks came from, as the article build reads them
const RES = process.env.RESEARCH ? path.resolve(process.env.RESEARCH) : null;
const VER = RES ? path.join(RES, 'framework-defaults', 'VERIFIED.md') : null;
const OAI = RES ? path.join(RES, 'verified-defaults-and-benchmarks-2026-10-26.json') : null;
const flat = x => x.replace(/\s+/g, ' ');
const read = p => (fs.existsSync(p) ? fs.readFileSync(p, 'utf8') : '');
const verified = VER ? read(VER) : '';
if (!RES) console.log('research notes check skipped (set RESEARCH=<folder> to run it). The check outputs are always checked.');
else if (!verified) notes.push(`VERIFIED.md not found under ${RES}`);
const sections = verified.split(/^## /m);
let oai = '', oaiExact = '';
if (RES && fs.existsSync(OAI)) {
  const j = JSON.parse(fs.readFileSync(OAI, 'utf8'));
  const claims = (j.verified.defaults.claims || []).filter(c => c.verified && /^D[12]/.test(c.id));
  oai = claims.map(c => [c.claim, c.version_or_date, c.exact_text_or_value, c.note].join(' ')).join(' ');
  oaiExact = (claims.find(c => c.id === 'D1') || {}).exact_text_or_value || '';
} else if (RES) notes.push('OpenAI research JSON not found, facts unchecked');
// the summary in framework-defaults/README.md, one section per framework under '### '
const readme = read(path.join(FD, 'README.md'));
if (!readme) notes.push('framework-defaults/README.md not found');
const readmeOf = prefix => readme.split(/^### /m).find(x => x.startsWith(prefix)) || '';
// '' = VERIFIED.md's header (method notes), 'openai' = the JSON claims, 'file:<path>' = one file under
// framework-defaults/, 'readme' = the whole README, else the VERIFIED.md section whose heading starts with src
const sectionOf = src => (src === 'openai' ? oai : src === '' ? sections[0] : src === 'readme' ? readme
  : src.startsWith('file:') ? read(path.join(FD, src.slice(5))) : sections.find(x => x.startsWith(src)) || '');
// the verbatim block of one finding (### <fid>), or OpenAI's quoted return line
function verbatimOf(src, fid) {
  if (src === 'openai') return oaiExact;
  const sub = sectionOf(src).split(/^### /m).find(x => x.startsWith(fid)) || '';
  const b = sub.match(/```\n([\s\S]*?)```/);
  return b ? b[1] : '';
}
const has = (src, e) => flat(sectionOf(src)).includes(flat(e));
// a framework folder's check scripts, outputs and requirements, for code identifiers
const folderFiles = (dir, re) => {
  const d = path.join(FD, dir);
  if (!fs.existsSync(d)) return '';
  return fs.readdirSync(d).filter(n => re.test(n)).map(n => read(path.join(d, n))).join('\n');
};
const folderText = dir => folderFiles(dir, /\.(md|py|txt)$/);
const outputText = dir => folderFiles(dir, /^output.*\.txt$/);
// numbers compare without thousands separators: 9,999 and 9_999 are both 9999
const digits = x => x.replace(/(\d)[,_](?=\d)/g, '$1');
const hasCode = (text, piece) => new RegExp((/^\w/.test(piece) ? '(^|[^\\w])' : '')
  + piece.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + (/\w$/.test(piece) ? '(?![\\w])' : '')).test(text);
const hasNumber = (text, n) => new RegExp(`(^|[^\\d.])${n}([^\\d]|$)`).test(digits(flat(text)));
// a version must be in the framework's own output, as a whole version number
const hasVersion = (text, v) => new RegExp(`(^|[^\\d.])${v.replace(/\./g, '\\.')}([^\\d.]|\\.(?!\\d)|$)`).test(text);
for (const r of ROWS) {
  if (RES) {
    if (!sectionOf(r.src)) notes.push(`${r.label}: no research section "${r.src}"`);
    else for (const e of r.ev) if (!has(r.src, e)) notes.push(`${r.label}: "${e}" not in its research section`);
  }
  if (!readmeOf(r.readme)) notes.push(`${r.label}: no section "${r.readme}" in framework-defaults/README.md`);
  for (const [src, e] of r.xev || []) if (!has(src, e)) notes.push(`${r.label}: "${e}" not in "${src}"`);
  const pool = (RES ? sectionOf(r.src) : '') + '\n' + readmeOf(r.readme) + '\n' + folderText(r.dir);
  const evText = [...(RES ? r.ev : []), ...(r.xev || []).map(x => x[1])].join(' | ');
  if (!outputText(r.dir).trim()) notes.push(`${r.label}: no check output in framework-defaults/${r.dir}`);
  for (const p of r.parts) {
    for (const l of p.ver) for (const run of l) for (const v of run.s.match(/\d+(\.\d+)+/g) || []) {
      if (!hasVersion(outputText(r.dir), v)) notes.push(`${r.label}: version "${run.s}" not in its check output`);
      if (RES && !has(r.src, run.s)) notes.push(`${r.label}: version "${run.s}" not in its research section`);
    }
    // code in a name or a cell must be in the summary or the framework's own scripts, as whole identifiers (so
    // handle_tool_error cannot pass on handle_tool_errors); a "..." marks a cut, and each piece around it must be there
    for (const l of [...p.name, ...p.note]) for (const run of l) if (run.mono)
      for (const piece of run.s.split('...').filter(Boolean))
        if (!hasCode(pool, piece)) notes.push(`${r.label}: "${run.s}" not in its checks`);
    // a limit number must sit in one of the row's own evidence strings, not just anywhere in a long file, where
    // a small number like 3 or 5 turns up by chance
    for (const l of p.lim.flat()) for (const n of digits(l).match(/\d+/g) || [])
      if (!hasNumber(evText, n)) notes.push(`${r.label}: limit number ${n} not in the row's evidence`);
    for (const x of p.lim.flat()) if (/\bnone\b/i.test(x)) notes.push(`${r.label}: write "No limit", not "${x}"`);
  }
  // every identifier in a setting must be in the summary or the framework's own scripts and outputs,
  // whole identifiers only, so max_llm_call cannot pass on max_llm_calls
  for (const k of r.knobs) for (const run of k) if (run.mono)
    for (const id of run.s.match(/[A-Za-z_][A-Za-z_.]*/g).filter(x => x !== 'N'))
      if (!new RegExp(`(^|[^\\w.])${id.replace(/\./g, '\\.')}(?![\\w])`).test(pool))
        notes.push(`${r.label}: setting identifier "${id}" not in its checks`);
  // a number in a grey line must be worked out from a check output (calc), or sit in the row's evidence
  let worked = null;
  if (r.calc) {
    const mt = read(path.join(FD, r.calc.file)).match(r.calc.re);
    if (!mt) notes.push(`${r.label}: calc pattern not found in ${r.calc.file}`);
    else worked = r.calc.fn(...mt.slice(1).map(Number));
  }
  for (const x of r.tail || []) for (const n of digits(x).match(/\d+/g) || [])
    if (!(worked !== null && Number(n) === worked) && !hasNumber(evText, n))
      notes.push(`${r.label}: number ${n} not backed: "${x}"`);
}
for (const g of GROUPS) for (const ex of g.ex || []) {
  const r = ROWS.find(x => x.g === g.key && x.label.startsWith(ex.from));
  if (!r) { notes.push(`example source "${ex.from}" is not a row in group ${g.key}`); continue; }
  // pieces joined by "..." must each be verbatim, in order, inside one block: one line of the framework's check
  // output, and with RESEARCH also the finding's verbatim block in the research notes
  const pieces = ex.text.split(/ ?\.\.\. ?/).filter(Boolean);
  const inOrder = block => {
    let at = 0;
    for (const piece of pieces) { const k = block.indexOf(piece, at); if (k < 0) return false; at = k + piece.length; }
    return true;
  };
  if (!outputText(r.dir).split('\n').some(inOrder)) notes.push(`example not verbatim (or out of order) on one line of ${r.dir}'s output: "${ex.text}"`);
  if (RES) {
    const block = verbatimOf(r.src, ex.fid);
    if (!block) notes.push(`${r.label}: no verbatim block for ${ex.fid}`);
    else if (!inOrder(block)) notes.push(`example not verbatim (or out of order) in ${r.label}'s research: "${ex.text}"`);
  }
}
for (const ft of FOOT) {
  const evs = (RES ? ft.ev || [] : []).concat(ft.rev || []);
  for (const [src, e] of evs) if (!has(src, e)) notes.push(`footer fact "${e}" not in "${src || 'header'}"`);
  if (RES) for (const run of ft.runs) if (run.mono && !verified.includes(run.s)) notes.push(`footer code "${run.s}" not in VERIFIED.md`);
  // the number must sit in one of the line's own evidence strings, not just anywhere in a long file
  for (const run of ft.runs) for (const n of digits(run.s).match(/\d+/g) || [])
    if (!evs.some(([, e]) => hasNumber(e, n))) notes.push(`footer number ${n} not backed: "${run.s}"`);
}
console.log('facts checked against the check outputs and README in framework-defaults/'
  + (RES ? `, ${path.basename(VER)} and ${path.basename(OAI)}` : ''));

// ---- header ----
const M = 52;
let y = 64;
T(M, y, 'FRAMEWORK DEFAULTS', { size: 28, family: MONO, fill: P.GOLD_TEXT, spacing: 3 });
f.raw(`<line x1="${M}" y1="${y + 22}" x2="${WD - M}" y2="${y + 22}" stroke="${P.GOLD}" stroke-width="2"/>`);
y += 92;
const HEAD = 'Eight frameworks handle one failed call three ways', HS = 44;
if (f.width(HEAD, HS, true) > WD - 2 * M) notes.push(`title too wide: ${Math.round(f.width(HEAD, HS, true))}`);
T(M, y, HEAD, { size: HS, weight: 700, key: true });
y += 54;
// one sentence per line
const DEK = ['The ticket service rejects a call with a 422 error.', 'Find your framework’s row.'];
DEK.forEach((x, i) => T(M, y + i * 38, x, { size: 30, fill: GREY }));
y += (DEK.length - 1) * 38 + 46;

// ---- columns ----
// widths from the widest cell in each: 'OpenAI Agents SDK' 308 at 32 bold and 'create_react_agent' 303 in Menlo 28,
// 'on_tool_error_callback' 371 in Menlo 28, 'AfterToolCallEvent hook' 372, 'then a forced final answer' 322 at 28.
// The setting lines span all three: Microsoft's is 1073 of the 1096 px.
const CX0 = 32, CX1 = WD - 32, PAD = 20;         // card edges, text starts 20 px in, at x = 52 like the header
const GAP = 35;
const CW = [328, 374, 324];                       // framework, what the model reads, limit
const COLX = [CX0 + PAD]; for (let i = 1; i < 3; i++) COLX.push(COLX[i - 1] + CW[i - 1] + GAP);
if (COLX[0] !== M) notes.push(`card text does not line up with the header: ${COLX[0]} vs ${M}`);
if (COLX[2] + CW[2] !== CX1 - PAD) notes.push(`columns do not fill the card: ${COLX[2] + CW[2]} vs ${CX1 - PAD}`);
const HSZ = 30;
HEADS.forEach((h, i) => { if (f.width(h, HSZ, true) > CW[i]) notes.push(`column heading wider than its column: "${h}"`); });

// ---- groups ----
const SZ = 28, NAME = 32, VSZ = 32, SET = 26, LH = 38;   // cell text, framework name, version line, setting, line step
const GT = 34, GSUB = 28;                         // group title and its lines
const EXH = 48, EXPAD = 18;                       // quote box height and side padding
const ROW_PT = 22, ROW_PB = 24;                   // row padding above the first line box and below the last
const KNOB_GAP = 6;                               // a little extra space above the setting lines
const HEAD_GAP = 4;                               // a little extra space under a row's bold header
const SUB_GAP = 24;                               // extra space between two entry points, with a dashed rule
const KNOB_MARGIN = 16;                           // a setting line keeps this much space from the card text edge
const GGAP = 30;                                  // space between group cards
const topRound = (x0, y0, x1, y1, r) =>
  `M${x0},${y1} L${x0},${y0 + r} Q${x0},${y0} ${x0 + r},${y0} L${x1 - r},${y0} Q${x1},${y0} ${x1},${y0 + r} L${x1},${y1} Z`;
const rowPads = [];
const BLOCK_GAP = 10;                             // extra space between two blocks in a limit cell
// a part's height in line steps, a limit cell's blocks a little apart
const partH = p => Math.max((p.name.length + p.ver.length) * LH, p.note.length * LH,
  p.lim.flat().length * LH + (p.lim.length - 1) * BLOCK_GAP);

function group(g, top) {
  const name = `group-${g.key}`;
  const bandName = `${name}-band`;
  // band: title, lines, then each quoted line under its label
  const titleY = top + 20 + GT * 0.76;
  const subY = g.sub.map((_, i) => titleY + 42 + i * 38);
  let cur = subY[subY.length - 1] + GSUB * 0.24;  // bottom of the last line box so far
  // a label sits 10 px over its own box and 26 px under the box before it, so it reads with the box it names
  const exs = (g.ex || []).map((ex, i) => {
    const label = `From ${ex.from}:`;
    const ly = cur + (i ? 26 : 18) + SZ * 0.76;   // label baseline
    const bt = ly + SZ * 0.24 + 10;               // box top
    const bw = ex.text.length * SZ * 0.602 + 2 * EXPAD;
    if (COLX[0] + bw > CX1 - PAD) notes.push(`${g.key}: quote box runs past the card text edge: ${Math.round(COLX[0] + bw)}`);
    cur = bt + EXH;
    return { ex, label, ly, bt, bw, base: bt + EXH / 2 + SZ * 0.36 };
  });
  const bandBot = cur + 22;
  // column headings in every card, so a phone reader still has them in view at the third card
  const headY = bandBot + 22 + HSZ * 0.76;
  const headBot = headY + HSZ * 0.24 + 16;
  // rows: an optional bold header, then each entry point's cells (the tallest of the three columns), then the
  // setting lines and grey lines across the row
  let ry = headBot;
  const rows = ROWS.filter(r => r.g === g.key);
  const rowGeo = rows.map((r, k) => {
    let yy = ry + ROW_PT + NAME * 0.76;           // the first baseline: a bold name or the bold header
    const hy = r.head ? yy : null;
    if (r.head) yy += LH + HEAD_GAP;
    const parts = r.parts.map((p, j) => {
      let rule = null;
      if (j) {
        // the dashed rule sits halfway between the last line box above and the first line box below
        const above = yy - LH + VSZ * 0.24, below = yy + SUB_GAP - SZ * 0.76;
        rule = (above + below) / 2;
        yy += SUB_GAP;
      }
      const h = partH(p);
      const geo = { p, j, first: yy, h, rule };
      yy += h;
      return geo;
    });
    const knobY = yy + KNOB_GAP;
    const nLines = r.knobs.length + (r.tail || []).length;
    const bot = knobY + (nLines - 1) * LH + SZ * 0.24 + ROW_PB;
    const geo = { r, k, top: ry, bot, hy, parts, knobY };
    ry = bot;
    return geo;
  });
  const bottom = ry;
  cont(name, CX0, top, CX1, bottom);
  cards.push({ name, x0: CX0, y0: top, x1: CX1, y1: bottom });

  // card, band, outline
  f.raw(`<rect x="${CX0}" y="${top}" width="${CX1 - CX0}" height="${bottom - top}" rx="12" fill="#FFFFFF"/>`);
  f.raw(`<path d="${topRound(CX0, top, CX1, bandBot, 12)}" fill="${g.band}"/>`);
  f.raw(`<line x1="${CX0}" y1="${bandBot}" x2="${CX1}" y2="${bandBot}" stroke="${g.stroke}" stroke-width="1.6"/>`);
  f.raw(`<rect x="${CX0}" y="${top}" width="${CX1 - CX0}" height="${bottom - top}" rx="12" fill="none" stroke="${g.stroke}" stroke-width="2.6"/>`);
  cont(bandName, CX0 + PAD, top, CX1 - PAD, bandBot);
  T(COLX[0], titleY, g.title, { size: GT, weight: 700, fill: g.ink, key: true }, bandName);
  g.sub.forEach((x, i) => {
    if (f.width(x, GSUB) > CX1 - CX0 - 2 * PAD) notes.push(`${g.key}: group line wider than the card: "${x}"`);
    T(COLX[0], subY[i], x, { size: GSUB, fill: GREY }, bandName);
  });
  exs.forEach((e, i) => {
    T(COLX[0], e.ly, e.label, { size: SZ, fill: GREY }, bandName);
    f.raw(`<rect x="${COLX[0]}" y="${e.bt}" width="${e.bw}" height="${EXH}" rx="8" fill="#FFFFFF" stroke="${P.RULE}" stroke-width="1.4"/>`);
    // the text must keep the full side padding inside the box, on the right as on the left
    cont(`${name}-ex${i}`, COLX[0] + EXPAD - 0.5, e.bt + 6, COLX[0] + e.bw - EXPAD + 0.5, e.bt + EXH - 6);
    T(COLX[0] + EXPAD, e.base, e.ex.text, { size: SZ, family: MONO, fill: P.INK }, `${name}-ex${i}`);
  });
  // headings, with a rule under them a little heavier than the rules between rows
  cont(`${name}-head`, CX0 + PAD, bandBot + 8, CX1 - PAD, headBot - 8);
  HEADS.forEach((h, i) => T(COLX[i], headY, h, { size: HSZ, weight: 700, fill: GREY }, `${name}-head`));
  f.raw(`<line x1="${CX0 + PAD}" y1="${headBot}" x2="${CX1 - PAD}" y2="${headBot}" stroke="${P.RULE}" stroke-width="1.8"/>`);

  // rows: a hairline between rows, cells aligned to the column grid
  rowGeo.forEach(({ r, k, top: rt, bot, hy, parts, knobY }) => {
    const rn = `${name}-r${k}`;
    if (k) f.raw(`<line x1="${CX0 + PAD}" y1="${rt}" x2="${CX1 - PAD}" y2="${rt}" stroke="${P.RULE}" stroke-width="1.2"/>`);
    cont(`${rn}-k`, COLX[0], rt + 8, CX1 - PAD - KNOB_MARGIN, bot - 8);
    if (r.head) {
      cont(`${rn}-h`, COLX[0], rt + 8, CX1 - PAD, hy + NAME * 0.24 + 2);
      T(COLX[0], hy, r.head, { size: NAME, weight: 700, key: true }, `${rn}-h`);
    }
    // a part's name is the framework's name in bold at 32, or, under a header, the entry point in bold at 28
    parts.forEach(({ p, j, first, h, rule }) => {
      const pn = `${rn}-p${j}`, cn = i => `${pn}-c${i}`;
      const pTop = first - NAME * 0.76 - 6, pBot = first + h - LH + VSZ * 0.24 + 6;
      for (let i = 0; i < 3; i++) cont(cn(i), COLX[i], pTop, COLX[i] + CW[i], pBot);
      if (rule != null) dashes.push({ y: rule, x0: COLX[0], x1: CX1 - PAD, row: r.label });
      if (rule != null) f.raw(`<line x1="${COLX[0]}" y1="${rule}" x2="${CX1 - PAD}" y2="${rule}" stroke="${P.RULE}" stroke-width="1.2" stroke-dasharray="5 6"/>`);
      let yy = first;
      p.name.forEach(l => {
        const o = { size: r.head ? SZ : NAME, weight: 700, key: true };
        if (lineW(l, o) > CW[0]) notes.push(`${r.label}: name line wider than its column`);
        runs(COLX[0], yy, l, o, cn(0)); yy += LH;
      });
      p.ver.forEach(l => {
        const o = { size: VSZ, fill: GREY };
        if (lineW(l, o) > CW[0]) notes.push(`${r.label}: version line wider than its column`);
        runs(COLX[0], yy, l, o, cn(0)); yy += LH;
      });
      p.note.forEach((l, i) => {
        const o = { size: SZ, fill: p.noteDim != null && i >= p.noteDim ? GREY : P.INK };
        if (lineW(l, o) > CW[1]) notes.push(`${r.label}: line wider than its column: "${l.map(x => x.s).join(' ')}"`);
        runs(COLX[1], first + i * LH, l, o, cn(1));
      });
      let li = 0;
      p.lim.forEach((block, bi) => block.forEach((x, i) => {
        if (f.width(x, SZ) > CW[2]) notes.push(`${r.label}: limit line wider than its column: "${x}"`);
        T(COLX[2], first + li * LH + bi * BLOCK_GAP, x, { size: SZ, fill: i ? GREY : P.INK }, cn(2)); li++;
      }));
    });
    // the settings as they are typed, the code in body ink: it is what the reader needs to act
    const ko = { size: SZ, fill: GREY, monoSize: SET, monoFill: P.INK };
    r.knobs.forEach((kl, i) => {
      if (COLX[0] + lineW(kl, ko) > CX1 - PAD - KNOB_MARGIN) notes.push(`${r.label}: setting line runs into the card margin`);
      runs(COLX[0], knobY + i * LH, kl, ko, `${rn}-k`);
    });
    (r.tail || []).forEach((x, i) => T(COLX[0], knobY + (r.knobs.length + i) * LH, x, { size: SZ, fill: GREY }, `${rn}-k`));
    // padding record: space above the first line box and below the last, for the consistency check
    const own = boxes.filter(b => b.in && b.in.startsWith(`${rn}-`));
    rowPads.push({ name: r.label, above: Math.min(...own.map(b => b.y0)) - rt, below: bot - Math.max(...own.map(b => b.y1)) });
  });
  return bottom;
}

GROUPS.forEach((g, i) => { y = group(g, y + (i ? GGAP : 0)); });

// ---- footer ----
const FS = 28, FMONO = 26, FLH = 36;
y += 60;
FOOT.forEach((ft, i) => {
  if (i && ft.gap) y += ft.gap;
  const o = { size: FS, fill: GREY, foot: true, monoSize: FMONO };
  const w = lineW(ft.runs, o);
  if (M + w > WD - M) notes.push(`footer line longer than one line: "${ft.runs.map(r => r.s).join(' ')}" (${Math.round(w)})`);
  runs(M, y, ft.runs, o, null); y += FLH;
});

// ---- checks ----
function check() {
  const out = [...new Set(notes)];
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const p = boxes[i], q = boxes[j];
    if (p.x0 < q.x1 && q.x0 < p.x1 && p.y0 < q.y1 && q.y0 < p.y1) out.push(`text overlap: "${p.s}" / "${q.s}"`);
  }
  // runs on one line need a visible gap, at least 5 px, unless the second is punctuation set tight on purpose
  for (let i = 0; i < boxes.length; i++) for (let j = 0; j < boxes.length; j++) {
    const p = boxes[i], q = boxes[j];
    if (i !== j && !q.tight && p.base === q.base && q.x0 >= p.x1 && q.x0 - p.x1 < 5) out.push(`runs touch: "${p.s}" / "${q.s}"`);
  }
  for (const b of boxes) if (b.in) {
    const k = conts[b.in];
    if (!k) { out.push(`no container ${b.in}`); continue; }
    if (b.x0 < k.x0 || b.x1 > k.x1 || b.y0 < k.y0 || b.y1 > k.y1) out.push(`text escapes ${b.in}: "${b.s}"`);
  }
  // text outside the cards must keep 8 px from every card
  for (const b of boxes) if (!b.in) for (const k of cards)
    if (b.x0 < k.x1 && k.x0 < b.x1 && b.y0 - 8 < k.y1 && k.y0 < b.y1 + 8) out.push(`text over ${k.name}: "${b.s}"`);
  // cards must not touch each other
  for (let i = 1; i < cards.length; i++) if (cards[i].y0 - cards[i - 1].y1 < 20) out.push(`${cards[i].name} too close to the card above`);
  // every row has the same padding above its first line and below its last, within 1 px
  const a0 = rowPads[0].above, b0 = rowPads[0].below;
  for (const p of rowPads) if (Math.abs(p.above - a0) > 1 || Math.abs(p.below - b0) > 1)
    out.push(`uneven row padding in ${p.name}: ${p.above.toFixed(1)} above, ${p.below.toFixed(1)} below`);
  // every cell's runs start on its column's left edge (aligned columns); setting lines and headers start on column 0
  for (const b of boxes) if (b.in && /-(c\d|k|h|head)$/.test(b.in)) {
    const lineStart = !boxes.some(x => x.in === b.in && x.base === b.base && x.x0 < b.x0);
    const edges = /-c\d$/.test(b.in) ? [COLX[+b.in.slice(-1)]] : /-(k|h)$/.test(b.in) ? [COLX[0]] : COLX;
    if (lineStart && !edges.some(e => Math.abs(b.x0 - e) <= 0.5)) out.push(`text off its column edge: "${b.s}"`);
  }
  // a dashed rule between two entry points keeps at least 12 px from the text above and below it
  for (const d of dashes) for (const b of boxes) if (b.x0 < d.x1 && d.x0 < b.x1 && b.y0 - 12 < d.y && d.y < b.y1 + 12)
    out.push(`text within 12 px of the dashed rule in ${d.row}: "${b.s}"`);
  if (ROWS.length !== 8) out.push(`expected 8 frameworks, have ${ROWS.length}`);
  return out;
}

(async () => {
  const problems = check();
  const warn = await f.render('framework-defaults', [], process.env.OUT || undefined, { gap: 0 });
  const all = [...problems, ...warn];
  if (all.length) { console.log('GEOMETRY:\n  ' + all.join('\n  ')); process.exitCode = 1; }
  else {
    console.log('geometry clean:', boxes.length, 'texts,', ROWS.length, 'rows in', cards.length, 'groups')
    console.log('row padding:', rowPads[0].above.toFixed(1), 'above,', rowPads[0].below.toFixed(1), 'below');
  }
})();
