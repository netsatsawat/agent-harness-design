# agent-harness-design

[![reproduce](https://github.com/netsatsawat/agent-harness-design/actions/workflows/reproduce.yml/badge.svg)](https://github.com/netsatsawat/agent-harness-design/actions/workflows/reproduce.yml)

An agent calls a ticket tool with priority "high". The ticket service accepts only P0, P1 or
P2, so it rejects the call. The Part 1 experiment on the OpenAI Agents SDK 0.24.0 compared three
replies to that rejection. When the harness sent back the SDK's default error line, OpenAI's
gpt-6-astra created the ticket with P1 in 0 of 20 runs. When the harness sent a short note that
named the three codes and what they mean, the same model got 20 of 20. The model and the task
stayed the same, and only the code around the model changed.

That code is the harness, and this repo is about designing it. You want an agent you can trust:
one that does what the user asked, stays inside its limits, recovers when a call fails and
leaves a record you can check. The harness code does most of that work, so if your team does
not design the harness, your framework's defaults do. The [framework
checks](part1-loop-and-readback/framework-defaults/README.md) show how far those defaults differ.
The same failed call stops the run in LangGraph, reaches the model as the raw exception in
Strands, and becomes a fixed line in the OpenAI Agents SDK.

This series splits the work into eight parts, one article each. Every part names its
patterns and pairs each one with its anti-pattern, the thing teams or framework defaults often
do instead. Every part also ships small runnable examples with tests. The patterns work with any
model, because each check makes a failure happen on purpose and then reads the trace.

| Word | What it means here |
|---|---|
| Agent | A model that calls tools in a loop. |
| Harness | The code around the model. It builds each request, runs the tools, writes what the model reads next, keeps memory, sets limits and asks for approvals. |
| Turn | One model call. A run is a series of turns that ends with a reply, an error or a limit. |
| Trace | The log of every model call and tool call in one run. |
| Anti-pattern | What teams or framework defaults often do instead of the pattern, and how to spot it in a trace. |

![The series map: eight parts of agent design, one article each. The model sits in the middle. Six parts of the harness surround it: loop and read-back, tools, context and memory, sub-agents and handoffs, recovery, and authority. Two parts of team work sit outside the harness: evidence before release and ownership after launch. Part 1 is highlighted.](part1-loop-and-readback/figures/series-map-part1.png)

*Six of the eight parts live in the harness code. The other two are team work: evidence before
release and ownership after launch.*

## The eight parts

| # | Part | The question it answers | Status |
|---|---|---|---|
| 1 | Loop and read-back | What does the model read back, and when does the run stop? | Available: [part1-loop-and-readback](part1-loop-and-readback) |
| 2 | Tools | Which tools does the model get? | Coming |
| 3 | Context and memory | What must the model always remember? | Coming |
| 4 | Sub-agents and handoffs | What must a sub-agent hand back? | Coming |
| 5 | Recovery | Is it safe to retry a write? | Coming |
| 6 | Authority | Where is each rule enforced? | Coming |
| 7 | Evidence before release (team work) | What proves a change works? | Coming |
| 8 | Ownership after launch (team work) | Who looks after the agent once it ships? | Coming |

One rule runs through all eight parts. The model chooses what to try, code enforces the limits
and rules, and your team decides what proves it works. The [Part 1
README](part1-loop-and-readback/README.md#a-harness-design-review) lists the pattern and the
anti-pattern for every part as a one-page design review.

## Run Part 1

You need Python 3.12 and [uv](https://docs.astral.sh/uv/). Run every command from the repo
root. None of these three calls a model.

```bash
uv venv --python 3.12 part1-loop-and-readback/.venv
uv pip install --python part1-loop-and-readback/.venv -r part1-loop-and-readback/examples/requirements-test.txt
part1-loop-and-readback/.venv/bin/python -m pytest part1-loop-and-readback/examples
```

The 27 tests drive the real OpenAI Agents SDK with a scripted stand-in model, so they need no
API key and no network. Without uv, create the venv with
`python3.12 -m venv part1-loop-and-readback/.venv`, then install with
`part1-loop-and-readback/.venv/bin/pip install -r part1-loop-and-readback/examples/requirements-test.txt`.

The [Part 1 README](part1-loop-and-readback/README.md) has the rest: the six patterns, the
experiment behind the numbers, a run on a local model with Ollama, an optional hosted run with a
spend cap, and the figures.

## How the repo is laid out

```
.github/workflows/reproduce.yml   CI: re-runs every Part 1 check, with no model calls
.python-version                   Python 3.12, used by CI
part1-loop-and-readback/
  README.md                       the Part 1 tutorial
  examples/                       the six patterns as small code, one agent with all six, pytest tests
  experiment/                     the experiment behind the Part 1 numbers, its pinned dependencies, its results
  expected/                       what check_error_strings.py prints under each SDK version
  framework-defaults/             the same failing tool in eight frameworks, every default left alone
  figures/                        the six Part 1 figures and the scripts that draw them
LICENSE                           MIT
```

Each part gets its own folder with its own README, pinned dependencies and venvs. Git ignores
the venvs, `node_modules`, the caches and the run folders that the Part 1 commands create, such
as `part1-loop-and-readback/experiment/smoke/`.

## How CI checks it

[`.github/workflows/reproduce.yml`](.github/workflows/reproduce.yml) runs on every push and
pull request, and none of its steps calls a model. For Part 1 it rebuilds the result tables from
the committed runs and diffs them, runs the example tests, diffs the SDK's error strings under
two SDK versions, and rebuilds the record of SDK defaults. The [Part 1
README](part1-loop-and-readback/README.md#how-ci-reproduces-the-numbers) lists each step with
the commands to run the same checks yourself.

## License

MIT. See [LICENSE](LICENSE).
