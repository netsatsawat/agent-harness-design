"""
What does an agent read when a tool fails, and does it change the outcome?

Since openai-agents 0.23.1 (2026-10-02) the SDK's default tool error handler returns one fixed
line for any tool failure. This script runs two tasks through the real SDK (Agent + Runner),
in three arms:

  default      the tool raises the server's validation error and the SDK's own default
               handler decides what the model reads (no failure_error_function is passed)
  old_default  the 0.22.3 default handler, copied verbatim into a failure_error_function:
               the same line plus "Error: {str(error)}". check_error_strings.py run under a
               second venv with the real 0.22.3 (../.venv-0.22.3) confirms it returns the same
               string, character for character, for every error this experiment produces
  note         a failure_error_function returns a short approved note: the field, the
               allowed values or format, and the next step (no secrets, no stack trace)

Two tasks, and the first call is NOT forced to fail:

  priority  "Open a high priority ticket: CSV export on the reports page times out for large
            date ranges." The schema types priority as a plain string with a vague
            description. The server accepts only P0 (critical), P1 (high), P2 (normal).
            Success = the first accepted call has priority P1 and a title about the export.
            The incident is plainly not an outage, so P0 is not a defensible reading of "high".
  phone     "Text the on-call engineer at (415) 555-0132 that checkout is down." `to` is a
            plain string described as "Phone number to send to." The server accepts only
            E.164 (+, country code, digits). Success = the first accepted call has to exactly
            +14155550132 and a message about checkout. A number the server accepts but that
            is not this one (+4155550132, a wrong country code) is wrong_value.

All arms share one system prompt. Its last sentence ("If a tool call returns an error, read it,
correct the call, and try again.") is this script's, not an SDK default (see sdk_defaults.txt).

Local models run through Ollama's OpenAI-compatible endpoint with the SDK's chat-completions
model class, thinking off (reasoning_effort="none", since Ollama's /v1 ignores a "think" field),
one model at a time (every model Ollama has loaded is unloaded first), and a seed per run so the
arms pair by seed.
The hosted model runs the way a reader would call it: Agent(model="<name>"), which goes through
the SDK's default provider (Responses API, no seed parameter), so its arms are unpaired.

Every hosted model call is priced from its usage and appended to hosted_spend.jsonl. A run stops
before it starts, or mid-run on the next model call, once total hosted spend in this folder would
pass the cap (HOSTED_CAP_USD, 10 USD). The OpenAI client reads OPENAI_API_KEY from the
environment, and nothing here stores a key. Logged text is scrubbed of API-key-shaped strings before
it is written.

Run from the part folder (part1-loop-and-readback):

  # no model calls: rebuild results.csv and tests.csv from the committed runs.jsonl
  .venv/bin/python experiment/harness_defaults.py analyze --out sweep
  # no model calls: write sdk_defaults.txt (needs ../.venv-0.22.3 or OLD_SDK_PYTHON)
  .venv/bin/python experiment/harness_defaults.py defaults
  # a local smoke run through Ollama (no API key, no spend), then its analysis
  .venv/bin/python experiment/harness_defaults.py run --local qwen3.5:0.8b --runs 2 --out smoke
  # hosted runs cost money: estimate first, then run (OPENAI_API_KEY from the environment)
  .venv/bin/python experiment/harness_defaults.py estimate --hosted gpt-6-astra --hosted-runs 20
  # the full sweep (20 runs per cell), resumable: finished runs in full/runs.jsonl are skipped
  .venv/bin/python experiment/harness_defaults.py run \
      --local qwen3.5:0.8b,qwen3.5:2b,qwen3.5:4b,qwen3.5:9b --runs 20 \
      --hosted gpt-6-astra,gpt-6.1-sol --hosted-runs 20 --out full

Pinned environment: requirements.lock.txt (openai-agents 0.24.0, openai 3.37.0, Python 3.12).
requirements-0.22.3.lock.txt pins openai-agents 0.22.3 for a second venv, used only by
check_error_strings.py.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import csv
import glob
import importlib.metadata
import inspect
import json
import math
import os
import re
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agents import (
    Agent, ModelSettings, OpenAIChatCompletionsModel, RunConfig, RunContextWrapper, RunHooks,
    Runner, function_tool,
)
from agents.exceptions import AgentsException, MaxTurnsExceeded
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.run_config import DEFAULT_MAX_TURNS
from agents.tool import _extract_tool_argument_json_error, default_tool_error_function
from agents.tool_context import ToolContext
from openai import AsyncOpenAI
from openai.types.shared import Reasoning

from check_error_strings import make_errors
from servers import ServerValidationError, sms_server, ticket_server

EXP_DIR = Path(__file__).resolve().parent
# the python of a second venv that holds openai-agents 0.22.3 (requirements-0.22.3.lock.txt)
OLD_VENV_PY = Path(os.environ.get(
    "OLD_SDK_PYTHON", EXP_DIR.parent / ".venv-0.22.3" / "bin" / "python"))
OLLAMA = "http://localhost:11434"
SPEND_LEDGER = EXP_DIR / "hosted_spend.jsonl"
HOSTED_CAP_USD = 10.00   # total hosted spend allowed across every run logged in this folder
ARMS = ["default", "old_default", "note"]
COMPARISONS = [("note", "default"), ("old_default", "default")]   # (arm a, arm b)
SEED_BASE = 1000
DESIGN = "v2"   # analyze reads only records of this design, and an earlier v1 used other tasks

# USD per 1M tokens, standard tier, from https://developers.openai.com/api/docs/pricing
# (checked 2026-10-26). Output tokens include reasoning tokens in the Responses API usage.
PRICES = {
    "gpt-6-astra": {"input": 10.00, "cached_input": 1.00, "output": 50.00},
    "gpt-6.1-sol": {"input": 2.00, "cached_input": 0.10, "output": 10.00},
}

INSTRUCTIONS = (
    "You are an operations assistant. Use the {tool} tool to complete the user's request. "
    "If a tool call returns an error, read it, correct the call, and try again."
)


# ---------------------------------------------------------------- redaction

_KEY_SHAPED = re.compile(r"\bsk-[A-Za-z0-9_*.\-]+")


def redact(text: str) -> str:
    """Scrub API-key-shaped strings (an AuthenticationError message carries a key's prefix and
    last 4 characters) and the exact key in the environment, if any."""
    key = os.environ.get("OPENAI_API_KEY") or ""
    if len(key) > 8:
        text = text.replace(key, "sk-REDACTED")
    return _KEY_SHAPED.sub("sk-REDACTED", text)


# ---------------------------------------------------------------- the tools

@dataclass
class RunLog:
    """Per-run context: what the server saw and what each model call cost."""
    calls: dict[str, dict] = field(default_factory=dict)      # call_id -> server verdict
    turns: list[dict] = field(default_factory=list)            # per model call usage
    notes_returned: int = 0                                     # approved notes handed back


def _call_server(ctx: ToolContext[RunLog], payload: dict, server: Callable) -> str:
    entry = {"args": payload, "verdict": None, "server_error": None}
    ctx.context.calls[ctx.tool_call_id] = entry
    try:
        result = server(**payload)
    except ServerValidationError as exc:
        entry["verdict"], entry["server_error"] = "rejected", str(exc)
        raise
    entry["verdict"] = "accepted"
    return json.dumps(result)


def create_ticket(ctx: ToolContext[RunLog], title: str, priority: str) -> str:
    """Create a support ticket.

    Args:
        title: Short summary of the issue.
        priority: Priority for the ticket.
    """
    return _call_server(ctx, {"title": title, "priority": priority}, ticket_server)


def send_sms(ctx: ToolContext[RunLog], to: str, message: str) -> str:
    """Send a text message.

    Args:
        to: Phone number to send to.
        message: The message text.
    """
    return _call_server(ctx, {"to": to, "message": message}, sms_server)


# The approved notes: field, allowed values or format, next step. Nothing else. The phone
# example is a London number from Ofcom's range kept for TV and film (020 7946 0xxx), so it is
# not a working line, not the answer, and does not hand over the +1 country code.
APPROVED_NOTES = {
    "priority": (
        "priority is not valid. Allowed values: P0 (critical), P1 (high), P2 (normal). "
        "Next step: call create_ticket again with priority set to one of these codes."
    ),
    "to": (
        "to is not valid. Use E.164 format: a plus sign, then the country code, then the rest "
        "of the number, digits only, with no spaces, dashes or brackets. Example: "
        "+442079460123. Next step: call send_sms again with to written in this format."
    ),
    "message": (
        "message is empty. Next step: call send_sms again with the text to send in message."
    ),
}


def approved_note(ctx: RunContextWrapper[RunLog], error: Exception) -> str:
    if isinstance(error, ServerValidationError) and error.field_name in APPROVED_NOTES:
        ctx.context.notes_returned += 1
        return APPROVED_NOTES[error.field_name]
    # anything we have no approved note for gets the SDK's own default line
    return default_tool_error_function(ctx, error)


def old_default_error_function(ctx: RunContextWrapper[Any], error: Exception) -> str:
    """openai-agents 0.22.3 default_tool_error_function, body copied verbatim (agents/tool.py,
    line 1966 of the 0.22.3 wheel). The helper it calls is unchanged in 0.24.0."""
    json_decode_error = _extract_tool_argument_json_error(error)
    if json_decode_error is not None:
        return (
            "An error occurred while parsing tool arguments. "
            "Please try again with valid JSON. "
            f"Error: {json_decode_error}"
        )
    return f"An error occurred while running the tool. Please try again. Error: {str(error)}"


@dataclass
class Task:
    name: str
    fn: Callable
    prompt: str
    target: str                         # the field the server validates strictly
    answer: str                         # the one right value for it
    other_ok: Callable[[dict], bool]    # the companion field is about the right thing

    def grade(self, args: dict | None) -> str:
        args = args or {}
        if args.get(self.target) != self.answer:
            return "wrong_value"
        return "success" if self.other_ok(args) else "wrong_other"


TASKS = {
    "priority": Task(
        "priority", create_ticket,
        "Open a high priority ticket: CSV export on the reports page times out for large "
        "date ranges.",
        "priority", "P1",
        lambda a: re.search(r"csv|export", str(a.get("title", "")), re.I) is not None,
    ),
    "phone": Task(
        "phone", send_sms,
        "Text the on-call engineer at (415) 555-0132 that checkout is down.",
        "to", "+14155550132",
        lambda a: re.search(r"check[\s-]?out", str(a.get("message", "")), re.I) is not None,
    ),
}


def make_tool(task: Task, arm: str):
    if arm == "default":
        return function_tool(task.fn)          # SDK default failure handler, untouched
    if arm == "old_default":
        return function_tool(task.fn, failure_error_function=old_default_error_function)
    return function_tool(task.fn, failure_error_function=approved_note)


def check_old_default() -> dict:
    """Run check_error_strings.py under the real 0.22.3 and compare with our copy."""
    if not OLD_VENV_PY.exists():
        return {"ok": False, "reason": f"{OLD_VENV_PY.name} of the 0.22.3 venv is missing. "
                "Create ../.venv-0.22.3 or set OLD_SDK_PYTHON."}
    out = subprocess.run(
        [str(OLD_VENV_PY), "-I", str(EXP_DIR / "check_error_strings.py")],
        capture_output=True, text=True, check=True, timeout=120,
    )
    real = json.loads(out.stdout)
    ours = {k: old_default_error_function(None, e) for k, e in make_errors().items()}
    mismatched = [k for k in ours if ours[k] != real["outputs"].get(k)]
    return {"ok": not mismatched, "mismatched": mismatched, "cases": len(ours), "real": real,
            "ours": ours}


# ---------------------------------------------------------------- hosted spend guard

class SpendCapReached(Exception):
    pass


def ledger_spend() -> float:
    if not SPEND_LEDGER.exists():
        return 0.0
    return sum(json.loads(line)["cost_usd"] for line in SPEND_LEDGER.read_text().splitlines()
               if line.strip())


def usage_dict(usage) -> dict:
    if usage is None:
        return {"input": 0, "cached_input": 0, "output": 0, "reasoning": 0}
    itd = getattr(usage, "input_tokens_details", None)
    otd = getattr(usage, "output_tokens_details", None)
    return {
        "input": int(getattr(usage, "input_tokens", 0) or 0),
        "cached_input": int(getattr(itd, "cached_tokens", 0) or 0) if itd else 0,
        "output": int(getattr(usage, "output_tokens", 0) or 0),
        "reasoning": int(getattr(otd, "reasoning_tokens", 0) or 0) if otd else 0,
    }


def cost_usd(model: str, u: dict) -> float:
    p = PRICES[model]
    fresh = max(u["input"] - u["cached_input"], 0)
    return (
        fresh * p["input"] + u["cached_input"] * p["cached_input"] + u["output"] * p["output"]
    ) / 1e6


class Recorder(RunHooks):
    """Logs usage per model call. For the hosted model, it also prices the call and enforces
    the cap."""

    def __init__(self, hosted_model: str | None, cap: float):
        self.hosted_model, self.cap = hosted_model, cap

    async def on_llm_end(self, context, agent, response) -> None:
        u = usage_dict(response.usage)
        turn = {"usage": u}
        if self.hosted_model:
            c = cost_usd(self.hosted_model, u)
            turn["cost_usd"] = c
            with SPEND_LEDGER.open("a") as f:
                f.write(json.dumps({"model": self.hosted_model, "usage": u, "cost_usd": c}) + "\n")
            if ledger_spend() >= self.cap:
                context.context.turns.append(turn)
                raise SpendCapReached(f"hosted spend reached the {self.cap:.2f} USD cap")
        context.context.turns.append(turn)


# ---------------------------------------------------------------- one run

def _turn_summaries(raw_responses) -> tuple[list[dict], dict[str, int]]:
    """What each model call emitted, and which call (turn) produced each tool call id."""
    turns, call_turn = [], {}
    for i, resp in enumerate(raw_responses, start=1):
        out = []
        for item in resp.output:
            kind = getattr(item, "type", type(item).__name__)
            if kind == "function_call":
                call_turn[item.call_id] = i
                out.append({"type": kind, "name": item.name, "arguments": item.arguments})
            elif kind == "message":
                text = "".join(getattr(c, "text", "") or "" for c in item.content)
                out.append({"type": kind, "text": text[:600]})
            else:
                out.append({"type": kind})
        turns.append({"turn": i, "output": out})
    return turns, call_turn


async def run_one(backend: str, model: str, task: Task, arm: str, seed: int, cap: float) -> dict:
    log = RunLog()
    if backend == "ollama":
        client = AsyncOpenAI(base_url=f"{OLLAMA}/v1", api_key="ollama")
        agent = Agent(
            name="ops", instructions=INSTRUCTIONS.format(tool=task.fn.__name__),
            tools=[make_tool(task, arm)],
            model=OpenAIChatCompletionsModel(model=model, openai_client=client),
            model_settings=ModelSettings(
                temperature=0.7, max_tokens=800, reasoning=Reasoning(effort="none"),
                extra_args={"seed": seed}, timeout=600,
            ),
        )
    else:
        # the way a reader calls it: model by name, SDK default settings and provider
        agent = Agent(
            name="ops", instructions=INSTRUCTIONS.format(tool=task.fn.__name__),
            tools=[make_tool(task, arm)], model=model,
        )
    hooks = Recorder(model if backend == "hosted" else None, cap)
    status, err, items, raw, final = "finished", None, [], [], None
    try:
        result = await Runner.run(
            agent, task.prompt, context=log, hooks=hooks,
            run_config=RunConfig(tracing_disabled=True),
        )   # max_turns not passed: the SDK default applies
        items, raw, final = result.new_items, result.raw_responses, result.final_output
    except MaxTurnsExceeded as exc:
        status, err = "max_turns", str(exc)
        if exc.run_data:
            items, raw = exc.run_data.new_items, exc.run_data.raw_responses
    except SpendCapReached as exc:
        status, err = "spend_cap", str(exc)
    except AgentsException as exc:
        status, err = "model_error", f"{type(exc).__name__}: {exc}"
        if getattr(exc, "run_data", None):
            items, raw = exc.run_data.new_items, exc.run_data.raw_responses
    except Exception as exc:   # connection errors, timeouts: not the model's doing
        cause = exc.__cause__ or exc.__context__
        if isinstance(cause, SpendCapReached):
            status, err = "spend_cap", str(cause)
        else:
            status, err = "infra_error", f"{type(exc).__name__}: {exc}"
    err = redact(err) if err else err

    turn_log, call_turn = _turn_summaries(raw)
    reads = {}
    for it in items:
        if isinstance(it, ToolCallOutputItem):
            ri = it.raw_item
            cid = ri.get("call_id") if isinstance(ri, dict) else getattr(ri, "call_id", None)
            reads[cid] = str(it.output)
    calls = []
    for it in items:
        if not isinstance(it, ToolCallItem):
            continue
        ri = it.raw_item
        cid, raw_args = getattr(ri, "call_id", None), getattr(ri, "arguments", "")
        try:
            args = json.loads(raw_args or "{}")
        except json.JSONDecodeError:
            args = None
        server = log.calls.get(cid)
        calls.append({
            "n": len(calls) + 1, "turn": call_turn.get(cid), "name": getattr(ri, "name", None),
            "arguments": raw_args, "args": args,
            "verdict": server["verdict"] if server else "not_invoked",
            "server_error": server["server_error"] if server else None,
            "model_read": reads.get(cid),
        })

    accepted = [c for c in calls if c["verdict"] == "accepted"]
    if status in ("infra_error", "spend_cap"):
        outcome = status
    elif accepted:
        outcome = task.grade(accepted[0]["args"])
    elif status in ("max_turns", "model_error"):
        outcome = status
    elif not calls:
        outcome = "no_call"
    else:
        outcome = "gave_up"
    first = calls[0] if calls else None
    tokens = {k: sum(t["usage"][k] for t in log.turns)
              for k in ("input", "cached_input", "output", "reasoning")}
    return {
        "event": "run", "design": DESIGN, "backend": backend, "model": model,
        "task": task.name, "arm": arm,
        "seed": seed if backend == "ollama" else None, "rep": seed - SEED_BASE,
        "sdk_version": importlib.metadata.version("openai-agents"),
        "max_turns": DEFAULT_MAX_TURNS, "status": status, "outcome": outcome,
        "first_call_value": (first["args"] or {}).get(task.target) if first else None,
        "accepted_value": (accepted[0]["args"] or {}).get(task.target) if accepted else None,
        "first_call_success": bool(
            first and first["verdict"] == "accepted" and task.grade(first["args"]) == "success"
        ),
        "first_call_failed": bool(first and first["verdict"] != "accepted"),
        "n_calls": len(calls), "calls": calls, "turns": len(raw),
        "reasoning_items": sum(
            1 for t in turn_log for o in t["output"] if o["type"] == "reasoning"
        ),
        "approved_notes_returned": log.notes_returned, "tokens": tokens,
        "cost_usd": round(sum(t.get("cost_usd", 0.0) for t in log.turns), 6),
        "final_output": (str(final)[:600] if final is not None else None),
        "turn_log": turn_log, "error": err,
    }


# ---------------------------------------------------------------- ollama housekeeping

def _ollama_post(path: str, body: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        f"{OLLAMA}{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def ollama_loaded() -> list[str]:
    with urllib.request.urlopen(f"{OLLAMA}/api/ps", timeout=30) as r:
        return [m["name"] for m in json.load(r).get("models", [])]


def ollama_unload_all() -> None:
    for name in ollama_loaded():
        _ollama_post("/api/generate", {"model": name, "keep_alive": 0})
    for _ in range(30):
        if not ollama_loaded():
            return
        time.sleep(1)


def ollama_has(model: str) -> bool:
    with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=30) as r:
        return model in {m["name"] for m in json.load(r).get("models", [])}


# ---------------------------------------------------------------- cost estimate

def hosted_history(model: str) -> list[dict]:
    """Every finished hosted run of this model in any output folder (v1 and v2 alike: the
    tasks are the same size, so they all calibrate cost per run)."""
    recs = []
    for path in glob.glob(str(EXP_DIR / "*" / "runs.jsonl")):
        for line in Path(path).read_text().splitlines():
            r = json.loads(line)
            if r.get("event") == "run" and r["backend"] == "hosted" and r["model"] == model \
                    and r["outcome"] not in ("infra_error", "spend_cap"):
                recs.append(r)
    return recs


def estimate_hosted(model: str, n_runs: int) -> dict:
    """Expected and worst-case cost for n_runs runs (each run = one model x task x arm x rep)."""
    p = PRICES[model]
    hist = hosted_history(model)
    if hist:
        # calibrated: mean cost per run so far. Worst case = every run uses all max_turns
        # calls at twice the dearest per-call cost seen (later calls carry more history)
        mean_run = sum(r["cost_usd"] for r in hist) / len(hist)
        worst_call = max(r["cost_usd"] / max(r["turns"], 1) for r in hist)
        basis = f"{len(hist)} earlier hosted runs (mean {mean_run:.4f} USD per run)"
        expected = n_runs * mean_run
        worst = n_runs * DEFAULT_MAX_TURNS * worst_call * 2
    else:
        # no history yet: assume 3 calls per run, 900 input and 400 output tokens per call
        # (output includes reasoning). Worst case = every run uses all max_turns calls at
        # 3000 input and 2000 output tokens each
        call = (900 * p["input"] + 400 * p["output"]) / 1e6
        worst_call = (3000 * p["input"] + 2000 * p["output"]) / 1e6
        basis = "assumed 3 calls/run, 900 in + 400 out tokens per call (no history yet)"
        expected = n_runs * 3 * call
        worst = n_runs * DEFAULT_MAX_TURNS * worst_call
    return {"expected": expected, "worst": worst, "basis": basis, "spent": ledger_spend()}


# ---------------------------------------------------------------- the sweep

def done_keys(path: Path) -> set:
    if not path.exists():
        return set()
    keys = set()
    for line in path.read_text().splitlines():
        r = json.loads(line)
        if r.get("event") == "run" and r.get("design") == DESIGN \
                and r["outcome"] not in ("infra_error", "spend_cap"):
            keys.add((r["model"], r["task"], r["arm"], r["rep"]))
    return keys


def _pick(arg: str, allowed: list[str], what: str) -> list[str]:
    picked = [x.strip() for x in arg.split(",") if x.strip()] if arg else list(allowed)
    bad = [x for x in picked if x not in allowed]
    if bad:
        raise SystemExit(f"unknown {what}: {bad}. Choose from {allowed}.")
    return picked


async def sweep(args) -> None:
    tasks = _pick(args.tasks, list(TASKS), "task")
    arms = _pick(args.arms, ARMS, "arm")
    if "old_default" in arms:
        chk = check_old_default()
        if not chk["ok"]:
            raise SystemExit(f"old_default does not match the real 0.22.3: {chk}")
        print(f"=== old_default matches the real openai-agents {chk['real']['version']} on "
              f"{chk['cases']} of {chk['cases']} errors", flush=True)
    out = EXP_DIR / args.out
    out.mkdir(exist_ok=True)
    runs_path = out / "runs.jsonl"
    done = done_keys(runs_path)
    logf = runs_path.open("a")

    def log(rec: dict) -> None:
        logf.write(redact(json.dumps(rec)) + "\n")
        logf.flush()

    def show(r: dict) -> None:
        calls = " | ".join(
            f"{json.dumps(c['args'])}->{c['verdict']}" for c in r["calls"]
        ) or "-"
        print(redact(f"  {r['model']:14s} {r['task']:8s} {r['arm']:11s} rep{r['rep']:<2d} "
                     f"{r['outcome']:11s} turns={r['turns']} calls: {calls}"), flush=True)

    plan = []
    for m in [m.strip() for m in (args.local or "").split(",") if m.strip()]:
        plan.append(("ollama", m, args.runs))
    if args.hosted:
        for hm in [x.strip() for x in args.hosted.split(",") if x.strip()]:
            plan.append(("hosted", hm, args.hosted_runs))

    for backend, model, n in plan:
        todo = [(rep, t, a) for rep in range(n) for t in tasks for a in arms
                if (model, t, a, rep) not in done]
        if not todo:
            print(f"=== {model}: nothing left to run", flush=True)
            continue
        if backend == "ollama":
            if not ollama_has(model):
                print(f"!!! {model} is not pulled, so it is skipped", flush=True)
                log({"event": "model_skipped", "model": model, "reason": "not pulled"})
                continue
            ollama_unload_all()
        else:
            if model not in PRICES:
                print(f"!!! no price for {model}, so it does not run. Add it to PRICES first.",
                      flush=True)
                return
            est = estimate_hosted(model, len(todo))
            print(f"=== hosted estimate for {len(todo)} runs of {model}: expected "
                  f"{est['expected']:.2f} USD, worst case {est['worst']:.2f} USD "
                  f"({est['basis']}). Already spent {est['spent']:.4f} USD, cap "
                  f"{args.cap:.2f} USD", flush=True)
            log({"event": "hosted_estimate", "model": model, "runs": len(todo), **est,
                 "cap": args.cap})
            if est["spent"] + est["expected"] > args.cap:
                print("!!! estimate exceeds the cap, so the hosted part does not run", flush=True)
                continue
        print(f"=== {model} ({backend}): {len(todo)} runs", flush=True)
        log({"event": "model_start", "model": model, "backend": backend})
        max_run_cost = 0.0
        for rep, tname, arm in todo:
            if backend == "hosted":
                spent = ledger_spend()
                if spent + max(max_run_cost * 1.5, 0.05) > args.cap:
                    print(f"!!! stopping: spent {spent:.4f} USD, next run could pass the "
                          f"cap", flush=True)
                    break
            rec = await run_one(backend, model, TASKS[tname], arm, SEED_BASE + rep, args.cap)
            max_run_cost = max(max_run_cost, rec["cost_usd"])
            log(rec)
            show(rec)
            if rec["outcome"] == "spend_cap":
                print("!!! spend cap reached, so the hosted part stops", flush=True)
                break
        log({"event": "model_done", "model": model})
        print(f"--- {model} done", flush=True)
        if backend == "ollama":
            ollama_unload_all()
    logf.close()
    analyze(args.out)


# ---------------------------------------------------------------- statistics

def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact test on [[a, b], [c, d]]."""
    r1, c1, n = a + b, a + c, a + b + c + d
    if n == 0:
        return 1.0

    def prob(x: int) -> float:
        return math.comb(r1, x) * math.comb(n - r1, c1 - x) / math.comb(n, c1)

    p_obs = prob(a)
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    return min(1.0, sum(prob(x) for x in range(lo, hi + 1) if prob(x) <= p_obs * (1 + 1e-9)))


def holm(ps: list[float]) -> list[float]:
    """Holm step-down adjusted p-values (family-wise error across all of ps)."""
    m, adj, running = len(ps), [0.0] * len(ps), 0.0
    for rank, i in enumerate(sorted(range(m), key=lambda j: ps[j])):
        running = max(running, min(1.0, (m - rank) * ps[i]))
        adj[i] = running
    return adj


def _counts(values) -> str:
    return " ".join(f"{v}:{n}" for v, n in collections.Counter(values).most_common())


def _compare(model: str, task: str, a: dict, b: dict, arm_a: str, arm_b: str) -> dict:
    """Arm a vs arm b on overall success and on fixes after a failed first call."""
    ok = lambda r: r["outcome"] == "success"   # noqa: E731
    row = {"model": model, "task": task, "arm_a": arm_a, "arm_b": arm_b}
    seeded = all(r["seed"] is not None for r in list(a.values()) + list(b.values()))
    if seeded:
        reps = sorted(set(a) & set(b))
        both_failed = [i for i in reps if a[i]["first_call_failed"] and b[i]["first_call_failed"]]
        oa = sum(ok(a[i]) and not ok(b[i]) for i in reps)
        ob = sum(not ok(a[i]) and ok(b[i]) for i in reps)
        fa = sum(ok(a[i]) and not ok(b[i]) for i in both_failed)
        fb = sum(not ok(a[i]) and ok(b[i]) for i in both_failed)
        row.update({
            "test": "McNemar exact (paired by seed)", "pairs": len(reps),
            "first_call_identical": sum(
                (a[i]["calls"][0]["arguments"] if a[i]["calls"] else None)
                == (b[i]["calls"][0]["arguments"] if b[i]["calls"] else None) for i in reps),
            "overall_a": f"{sum(ok(a[i]) for i in reps)}/{len(reps)}",
            "overall_b": f"{sum(ok(b[i]) for i in reps)}/{len(reps)}",
            "overall_discordant": f"a only {oa}, b only {ob}",
            "overall_p": mcnemar_exact(oa, ob), "overall_n": len(reps),
            "fix_a": f"{sum(ok(a[i]) for i in both_failed)}/{len(both_failed)}",
            "fix_b": f"{sum(ok(b[i]) for i in both_failed)}/{len(both_failed)}",
            "fix_discordant": f"a only {fa}, b only {fb}",
            "fix_p": mcnemar_exact(fa, fb), "fix_n": len(both_failed),
        })
    else:
        ra, rb = list(a.values()), list(b.values())
        sa, sb = sum(map(ok, ra)), sum(map(ok, rb))
        fa_runs = [r for r in ra if r["first_call_failed"]]
        fb_runs = [r for r in rb if r["first_call_failed"]]
        fa, fb = sum(map(ok, fa_runs)), sum(map(ok, fb_runs))
        row.update({
            "test": "Fisher exact (unpaired)", "pairs": "", "first_call_identical": "",
            "overall_a": f"{sa}/{len(ra)}", "overall_b": f"{sb}/{len(rb)}",
            "overall_discordant": "",
            "overall_p": fisher_exact(sa, len(ra) - sa, sb, len(rb) - sb),
            "overall_n": min(len(ra), len(rb)),
            "fix_a": f"{fa}/{len(fa_runs)}", "fix_b": f"{fb}/{len(fb_runs)}",
            "fix_discordant": "",
            "fix_p": fisher_exact(fa, len(fa_runs) - fa, fb, len(fb_runs) - fb),
            "fix_n": min(len(fa_runs), len(fb_runs)),
        })
    return row


def analyze(out_name: str) -> None:
    out = EXP_DIR / out_name
    runs, excluded = {}, 0
    for line in (out / "runs.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r.get("event") != "run" or r.get("design") != DESIGN:
            continue
        if r["outcome"] in ("infra_error", "spend_cap"):
            excluded += 1
            continue
        runs[(r["model"], r["task"], r["arm"], r["rep"])] = r
    if not runs:
        print("no runs to analyze")
        return
    models = list(dict.fromkeys(k[0] for k in runs))
    rows, tests = [], []
    for model in models:
        for tname in TASKS:
            cell = {arm: {k[3]: r for k, r in runs.items() if k[:3] == (model, tname, arm)}
                    for arm in ARMS}
            for arm in ARMS:
                rs = list(cell[arm].values())
                if not rs:
                    continue
                n = len(rs)
                succ = sum(r["outcome"] == "success" for r in rs)
                fcf = [r for r in rs if r["first_call_failed"]]
                fixed = sum(r["outcome"] == "success" for r in fcf)
                lo, hi = wilson(succ, n)
                flo, fhi = wilson(fixed, len(fcf))
                count = lambda o: sum(r["outcome"] == o for r in rs)   # noqa: E731
                rows.append({
                    "model": model, "backend": rs[0]["backend"], "task": tname, "arm": arm,
                    "runs": n, "success": succ, "success_rate": round(succ / n, 3),
                    "success_ci_lo": round(lo, 3), "success_ci_hi": round(hi, 3),
                    "first_call_success": sum(r["first_call_success"] for r in rs),
                    "first_call_failed": len(fcf), "fixed_after_failure": fixed,
                    "fix_rate": round(fixed / len(fcf), 3) if fcf else "",
                    "fix_ci_lo": round(flo, 3) if fcf else "",
                    "fix_ci_hi": round(fhi, 3) if fcf else "",
                    "wrong_value": count("wrong_value"), "wrong_other": count("wrong_other"),
                    "gave_up": count("gave_up"), "max_turns": count("max_turns"),
                    "no_call": count("no_call"), "model_error": count("model_error"),
                    "first_call_values": _counts(
                        r["first_call_value"] for r in rs if r["n_calls"]),
                    "wrong_values": _counts(
                        r["accepted_value"] for r in rs if r["outcome"] == "wrong_value"),
                    "mean_turns": round(sum(r["turns"] for r in rs) / n, 2),
                    "mean_tokens": round(sum(
                        r["tokens"]["input"] + r["tokens"]["output"] for r in rs) / n, 1),
                    "cost_usd": round(sum(r["cost_usd"] for r in rs), 4),
                })
            for arm_a, arm_b in COMPARISONS:
                if cell[arm_a] and cell[arm_b]:
                    tests.append(_compare(model, tname, cell[arm_a], cell[arm_b], arm_a, arm_b))
    # Holm across every p-value in this file that had data, so one p<0.05 cell among many
    # is not read as a finding on its own
    family = [(i, k) for i, t in enumerate(tests) for k in ("overall", "fix") if t[f"{k}_n"]]
    adjusted = holm([tests[i][f"{k}_p"] for i, k in family])
    for t in tests:
        for k in ("overall", "fix"):
            t[f"{k}_p_holm"] = ""
            t[f"{k}_p"] = round(t[f"{k}_p"], 4)
    for (i, k), p in zip(family, adjusted):
        tests[i][f"{k}_p_holm"] = round(p, 4)
    for t in tests:
        t["holm_family_size"] = len(family)

    with (out / "results.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    if tests:
        with (out / "tests.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(tests[0]))
            w.writeheader()
            w.writerows(tests)
    print(f"\n{'model':14s} {'task':8s} {'arm':11s} {'success':>12s} {'1st ok':>6s} "
          f"{'1st fail':>8s} {'fixed':>5s} {'wrong':>5s} {'no_call':>7s} {'turns':>5s} "
          f"{'cost':>7s}  first-call values")
    for r in rows:
        print(f"{r['model']:14s} {r['task']:8s} {r['arm']:11s} "
              f"{r['success']:>3d}/{r['runs']:<2d} [{r['success_ci_lo']:.2f},"
              f"{r['success_ci_hi']:.2f}] {r['first_call_success']:>6d} "
              f"{r['first_call_failed']:>8d} {r['fixed_after_failure']:>5d} "
              f"{r['wrong_value'] + r['wrong_other']:>5d} {r['no_call']:>7d} "
              f"{r['mean_turns']:>5.1f} {r['cost_usd']:>7.4f}  {r['first_call_values']}")
    for t in tests:
        print(f"{t['model']:14s} {t['task']:8s} {t['arm_a']} vs {t['arm_b']}, {t['test']}: "
              f"overall {t['overall_a']} vs {t['overall_b']} p={t['overall_p']} "
              f"(Holm {t['overall_p_holm']}), fix {t['fix_a']} vs {t['fix_b']} "
              f"p={t['fix_p']} (Holm {t['fix_p_holm']})")
    print(f"Holm family: {len(family)} p-values in tests.csv")
    print(f"excluded runs (infra_error/spend_cap): {excluded}")
    print(f"wrote {out / 'results.csv'}" + (f" and {out / 'tests.csv'}" if tests else ""))


# ---------------------------------------------------------------- sdk defaults record

def write_defaults() -> None:
    import agents
    import agents.run_config as rc
    import agents.tool as tool_mod

    ver = importlib.metadata.version("openai-agents")
    src = inspect.getsource(default_tool_error_function)
    line = inspect.getsourcelines(default_tool_error_function)[1]
    mt_line = next(
        i for i, s in enumerate(Path(rc.__file__).read_text().splitlines(), 1)
        if s.startswith("DEFAULT_MAX_TURNS")
    )
    errs = make_errors()
    new_out = {k: default_tool_error_function(None, e) for k, e in errs.items()}
    chk = check_old_default()
    if "real" not in chk:
        raise SystemExit(chk["reason"])
    real = chk["real"]
    old_file = real["file"]   # already relative to site-packages (check_error_strings.py)
    site = Path(agents.__file__).resolve().parent.parent
    rel = lambda p: Path(p).resolve().relative_to(site).as_posix()   # noqa: E731
    side_by_side = "\n".join(
        f"   [{k}]\n     {ver}: {new_out[k]}\n     {real['version']}: {real['outputs'][k]}"
        for k in ("priority_422", "phone_422", "bad_json_sdk")
    )
    verdict = (
        f"MATCH on {chk['cases']} of {chk['cases']} errors (both 422s, bad JSON as the SDK "
        f"raises it, bad JSON with the decode error attached, a plain RuntimeError)"
        if chk["ok"] else f"MISMATCH on {chk['mismatched']}"
    )
    text = f"""openai-agents defaults, read from the installed source
installed: openai-agents {ver} (from requirements.lock.txt)
for comparison: openai-agents {real['version']} in a second venv (from
requirements-0.22.3.lock.txt), used only by check_error_strings.py
Paths below are relative to each venv's site-packages folder.

1. Default tool error string
   {rel(tool_mod.__file__)}, line {line}:

{src}
   What the model reads for any exception a function tool raises when no
   failure_error_function is passed (checked by calling it on this experiment's errors):
   "{new_out['priority_422']}"

2. Default max_turns
   DEFAULT_MAX_TURNS = {rc.DEFAULT_MAX_TURNS}   ({rel(rc.__file__)}, line {mt_line})
   Runner.run uses it when max_turns is not passed. A turn is one model call, so a run is at
   most {rc.DEFAULT_MAX_TURNS} model calls before MaxTurnsExceeded.
   Choice: kept at the SDK default. It bounds a run at 10 model calls, so a run that never
   succeeds still ends. The script never passes max_turns.

3. The change, read from the real {real['version']} install
   {old_file}, line {real['line']}:

{real['source']}
   0.22.3 was uploaded 2026-09-17 and 0.23.1 on 2026-10-02. No 0.23.0 exists on PyPI, so
   0.22.3 -> 0.23.1 is the step. DEFAULT_MAX_TURNS was 10 in both.
   What each version returns for this experiment's errors (check_error_strings.py):
{side_by_side}

   The "old_default" arm copies the 0.22.3 function body into a failure_error_function run
   under {ver}. Compared with the real {real['version']} on the same errors: {verdict}.
   It is the old string reproduced in the current SDK, so the arms differ only in this string.

   Caveat: the servers here raise an error whose str() holds the whole 422 body, the way SDK
   clients such as Twilio's or Stripe's carry the server's message. That is the generous case
   for the old default. A tool that calls httpx or requests raise_for_status() raises an
   error whose str() holds only the status line and the URL, so the old default would have
   shown no allowed values. The old_default arm does not show that the old default always
   told the model the allowed values.

4. Other SDK defaults this experiment runs on
   - Agent(model="<name>") with no model_settings: for any name outside the SDK's gpt-5*
     patterns (gpt-6-astra and gpt-6.1-sol included) the agent gets ModelSettings(), so no
     temperature, reasoning effort or seed is sent and the API's own defaults apply
     (agents/models/default_models.py, get_default_model_settings). In the sweep, under these
     settings, gpt-6-astra reported reasoning tokens on 10 of its 370 calls (150 tokens in
     all) and gpt-6.1-sol on 9 of its 377 calls (136 tokens in all).
   - A model given by name goes through the Responses API (_use_responses_by_default = True).
     The Responses API takes no seed, so hosted arms are unpaired (Fisher exact).
   - The SDK's default model when none is given: gpt-5.6-luna (OPENAI_DEFAULT_MODEL overrides).
   - Tracing is on by default and uploads traces to OpenAI. This script turns it off with
     RunConfig(tracing_disabled=True). It does not change what the model sees.
   - run_config.tool_error_formatter is None by default, so nothing rewrites the fixed line.
   - OPENAI_AGENTS_DONT_LOG_TOOL_DATA defaults to on, so the SDK raises bad tool-argument JSON
     without the decode error attached. Both versions then use their generic line for it.

5. Local backend (Ollama 0.33.3, OpenAI-compatible /v1 endpoint)
   OpenAIChatCompletionsModel with ModelSettings(temperature=0.7, max_tokens=800,
   reasoning=Reasoning(effort="none"), extra_args={{"seed": seed}}). reasoning_effort="none"
   turns qwen3.5 thinking off. An extra_body "think": false is ignored on /v1 (probed
   2026-10-26: the reply still carried a reasoning field).

6. What this script adds on top of the SDK (not defaults, so state them with any result)
   - The system prompt, shared by every arm:
     "{INSTRUCTIONS}"
     Its last sentence is this script's, not the SDK's. In the default arm it adds to the
     SDK's own "Please try again", which can stretch retry loops. Every arm shares it, so the
     comparison holds, but a reader should not think the prompt alone caused the loops.
   - The approved notes (the "note" arm), verbatim:
{chr(10).join(f'     {k}: "{v}"' for k, v in APPROVED_NOTES.items())}
   - Statistics: one test per comparison (note vs default, old_default vs default) per model
     and task, on overall success and on fixes after a failed first call. The full sweep makes
     6 models x 2 tasks x 2 comparisons x 2 tests = 48 p-values. Each row of tests.csv carries
     Holm-adjusted values across all 48, so one p<0.05 cell is not read as a finding.
"""
    (EXP_DIR / "sdk_defaults.txt").write_text(text)
    print(text)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("defaults")
    r = sub.add_parser("run")
    r.add_argument("--local", default="", help="comma-separated Ollama tags, run in order")
    r.add_argument("--runs", type=int, default=20, help="runs per local cell")
    r.add_argument("--hosted", default="", help="comma-separated hosted OpenAI model names")
    r.add_argument("--hosted-runs", type=int, default=20, help="runs per hosted cell")
    r.add_argument("--tasks", default="", help=f"subset of {list(TASKS)} (default: all)")
    r.add_argument("--arms", default="", help=f"subset of {ARMS} (default: all)")
    r.add_argument("--cap", type=float, default=HOSTED_CAP_USD)
    r.add_argument("--out", default="sweep")
    e = sub.add_parser("estimate")
    e.add_argument("--hosted", default="gpt-6-astra")
    e.add_argument("--hosted-runs", type=int, default=20)
    a = sub.add_parser("analyze")
    a.add_argument("--out", default="sweep")
    args = ap.parse_args()
    if args.cmd == "defaults":
        write_defaults()
    elif args.cmd == "run":
        asyncio.run(sweep(args))
    elif args.cmd == "estimate":
        if args.hosted not in PRICES:
            raise SystemExit(f"no price for {args.hosted}. Add it to PRICES first.")
        n = args.hosted_runs * len(TASKS) * len(ARMS)
        est = estimate_hosted(args.hosted, n)
        print(f"{n} runs of {args.hosted}: expected {est['expected']:.2f} USD, worst case "
              f"{est['worst']:.2f} USD ({est['basis']}). Already spent {est['spent']:.4f} "
              f"USD, cap {HOSTED_CAP_USD:.2f} USD")
    else:
        analyze(args.out)


if __name__ == "__main__":
    main()
