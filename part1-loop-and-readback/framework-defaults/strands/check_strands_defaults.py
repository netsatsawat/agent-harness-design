"""
What a Strands Agents model reads after a tool fails, with every Agent default left alone.

No network, no API key, no model call. The model is a scripted fake built on the SDK's own
extension point (a subclass of strands.models.Model that streams the same events a provider
streams). The agent loop, the @tool decorator, the tool executor and the hooks are the real
installed ones.

Run from this folder, with the venv from requirements.txt (strands-agents==1.62.0):

    python -I -u check_strands_defaults.py > output.txt 2>&1

Sections 1 to 5 use Agent(model=fake, tools=[create_ticket]) and agent(prompt) with nothing
else set. Section 6 turns on one knob at a time and is labelled as such.
"""

from __future__ import annotations

import os

# No provider keys, no telemetry, before strands is imported.
for _k in list(os.environ):
    if _k.startswith(("AWS_", "OPENAI_", "ANTHROPIC_", "GEMINI_", "GOOGLE_", "MISTRAL_",
                      "LITELLM_", "LLAMA_", "WRITER_")):
        del os.environ[_k]
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["DO_NOT_TRACK"] = "1"

import socket  # noqa: E402

_real_connect = socket.socket.connect


def _no_network(self, address):  # any TCP/UDP connect fails loudly
    if self.family in (socket.AF_INET, socket.AF_INET6):
        raise RuntimeError(f"network blocked by check script: {address!r}")
    return _real_connect(self, address)


socket.socket.connect = _no_network

import asyncio  # noqa: E402
import contextlib  # noqa: E402
import copy  # noqa: E402
import importlib.metadata  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
from typing import Any  # noqa: E402

import strands  # noqa: E402,F401
from strands import Agent, tool  # noqa: E402
from strands.hooks import AfterToolCallEvent  # noqa: E402
from strands.models import Model  # noqa: E402
from strands.types.exceptions import ModelThrottledException  # noqa: E402


# ---- copied verbatim from part1-loop-and-readback/experiment/servers.py ----------------------
class ServerValidationError(Exception):
    """What the API client raises on HTTP 422, with a FastAPI/pydantic-style body."""

    def __init__(self, field_name: str, value: Any, err_type: str, msg: str,
                 ctx: dict | None = None):
        self.field_name, self.value = field_name, value
        detail = {"type": err_type, "loc": ["body", field_name], "msg": msg, "input": value}
        if ctx:
            detail["ctx"] = ctx
        super().__init__(f"422 Unprocessable Entity: {json.dumps({'detail': [detail]})}")


def ticket_server(title: str, priority: str) -> dict:
    """Accepts only the codes P0 (critical), P1 (high), P2 (normal)."""
    if priority not in ("P0", "P1", "P2"):
        raise ServerValidationError(
            "priority", priority, "enum", "Input should be 'P0', 'P1' or 'P2'",
            {"expected": "'P0', 'P1' or 'P2'"},
        )
    return {"id": "TCK-1042", "title": title, "priority": priority, "status": "open"}
# -----------------------------------------------------------------------------------------------

TOOL_RUNS = {"create_ticket": 0}


@tool
def create_ticket(title: str, priority: str) -> str:
    """Create a support ticket.

    Args:
        title: Short summary of the issue.
        priority: Priority for the ticket.
    """
    TOOL_RUNS["create_ticket"] += 1
    return json.dumps(ticket_server(title, priority))


# ---- scripted fake model ----------------------------------------------------------------------
def tool_call(name: str, input_json: str, tool_use_id: str) -> list[dict]:
    return [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockStart": {"start": {"toolUse": {"toolUseId": tool_use_id, "name": name}}}},
        {"contentBlockDelta": {"delta": {"toolUse": {"input": input_json}}}},
        {"contentBlockStop": {}},
        {"messageStop": {"stopReason": "tool_use"}},
        {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
                      "metrics": {"latencyMs": 1}}},
    ]


def text_reply(text: str) -> list[dict]:
    return [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockDelta": {"delta": {"text": text}}},
        {"contentBlockStop": {}},
        {"messageStop": {"stopReason": "end_turn"}},
        {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
                      "metrics": {"latencyMs": 1}}},
    ]


class ScriptedModel(Model):
    """Plays back a script; records every messages list the loop sends it."""

    def __init__(self, script):
        self.script = script  # script(call_index) -> list of stream events, or raises
        self.received: list[list[dict]] = []
        self.config = {"model_id": "scripted-fake"}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> Any:
        return self.config

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError("not used")
        yield  # pragma: no cover

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        idx = len(self.received)
        self.received.append(copy.deepcopy(messages))
        for event in self.script(idx):
            yield event


GOOD_ARGS = json.dumps({"title": "CSV export times out", "priority": "high"})
PROMPT = "Open a high-priority ticket: CSV export times out."


def show(label: str, obj: Any) -> None:
    print(f"{label}:")
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=repr))


def one_failed_call(section: str, input_json: str) -> None:
    """Turn 1 calls create_ticket with input_json; turn 2 replies with text."""
    print(f"\n===== {section} =====")
    print(f"turn 1 tool input sent by the fake model: {input_json}")
    TOOL_RUNS["create_ticket"] = 0
    model = ScriptedModel(
        lambda i: tool_call("create_ticket", input_json, "tooluse_1") if i == 0
        else text_reply("ok")
    )
    agent = Agent(model=model, tools=[create_ticket])  # every other argument left at default
    try:
        result = agent(PROMPT)
    except Exception as exc:  # would mean the run stopped before turn 2
        print(f"\nRUN STOPPED WITH EXCEPTION before turn 2: {type(exc).__name__}: {exc}")
        return
    print()
    print(f"run raised to caller: no; stop_reason={result.stop_reason!r}")
    print(f"model calls: {len(model.received)}; create_ticket function body ran: "
          f"{TOOL_RUNS['create_ticket']} time(s)")
    turn2_last = model.received[1][-1]
    show("turn 2: last message the model received", turn2_last)
    tr = turn2_last["content"][0]["toolResult"]
    print(f"turn 2: role={turn2_last['role']!r} status={tr['status']!r}")
    print(f"turn 2: text verbatim -> {tr['content'][0]['text']}")


def loop_forever_defaults(cap: int) -> None:
    print(f"\n===== 4. Default turn limit: a model that calls the failing tool forever (cap {cap}) =====")
    print(f"sys.getrecursionlimit()={sys.getrecursionlimit()}")
    model = ScriptedModel(
        lambda i: tool_call("create_ticket", GOOD_ARGS, f"tooluse_{i}") if i < cap
        else text_reply("giving up (script cap reached)")
    )
    agent = Agent(model=model, tools=[create_ticket])  # all defaults
    printed = io.StringIO()  # the default callback handler prints a line per tool call; hide it
    try:
        with contextlib.redirect_stdout(printed):
            result = agent(PROMPT)
        print(f"no exception; stop_reason={result.stop_reason!r}; model calls={len(model.received)}")
        print("=> the loop ran until the fake model itself stopped; no turn limit fired")
    except Exception as exc:
        msg = str(exc)
        print(f"raised to caller: {type(exc).__name__}: {msg[:300]}")
        cause = exc.__cause__
        if cause is not None:
            print(f"  __cause__: {type(cause).__name__}: {str(cause)[:300]}")
        print(f"  model calls before the raise: {len(model.received)}")


def knob_limits_turns() -> None:
    print("\n===== 6a. KNOB (not default): agent(prompt, limits={'turns': 3}) =====")
    model = ScriptedModel(lambda i: tool_call("create_ticket", GOOD_ARGS, f"tooluse_{i}"))
    agent = Agent(model=model, tools=[create_ticket], callback_handler=None)
    result = agent(PROMPT, limits={"turns": 3})
    print(f"no exception; stop_reason={result.stop_reason!r}; model calls={len(model.received)}")
    print(f"str(result) = {str(result)!r}")
    show("AgentResult.message (last message in history)", result.message)


def knob_after_tool_hook() -> None:
    print("\n===== 6b. KNOB (not default): AfterToolCallEvent hook rewrites the result =====")
    model = ScriptedModel(
        lambda i: tool_call("create_ticket", GOOD_ARGS, "tooluse_1") if i == 0
        else text_reply("ok")
    )
    agent = Agent(model=model, tools=[create_ticket], callback_handler=None)
    seen = {}

    def rewrite(event: AfterToolCallEvent) -> None:
        seen["exception"] = repr(event.exception)
        seen["result_before"] = copy.deepcopy(event.result)
        if isinstance(event.exception, ServerValidationError):
            event.result = {
                "toolUseId": event.result["toolUseId"],
                "status": "error",
                "content": [{"text": (
                    f"The ticket service rejected {event.exception.field_name}="
                    f"{event.exception.value!r}. Allowed values: P0 (critical), P1 (high), "
                    "P2 (normal).")}],
            }

    agent.hooks.add_callback(AfterToolCallEvent, rewrite)
    agent(PROMPT)
    print(f"hook saw event.exception = {seen['exception']}")
    show("hook saw event.result before rewrite", seen["result_before"])
    show("turn 2: last message the model received", model.received[1][-1])


def knob_hitl() -> None:
    from strands.vended_interventions.hitl import HumanInTheLoop

    print("\n===== 6c. KNOB (not default): interventions=[HumanInTheLoop()] =====")
    TOOL_RUNS["create_ticket"] = 0
    model = ScriptedModel(
        lambda i: tool_call("create_ticket", GOOD_ARGS, "tooluse_1") if i == 0
        else text_reply("ok")
    )
    agent = Agent(model=model, tools=[create_ticket], callback_handler=None,
                  interventions=[HumanInTheLoop()])
    result = agent(PROMPT)
    print(f"no ask callback: stop_reason={result.stop_reason!r}; model calls={len(model.received)}; "
          f"tool body ran {TOOL_RUNS['create_ticket']} time(s)")
    for it in result.interrupts or []:
        print(f"  interrupt name={it.name!r} reason={it.reason!r}")

    print("\n-- HumanInTheLoop(ask=lambda prompt: 'n'), the human says no --")
    TOOL_RUNS["create_ticket"] = 0
    model = ScriptedModel(
        lambda i: tool_call("create_ticket", GOOD_ARGS, "tooluse_1") if i == 0
        else text_reply("ok")
    )
    agent = Agent(model=model, tools=[create_ticket], callback_handler=None,
                  interventions=[HumanInTheLoop(ask=lambda prompt, **kw: "n")])
    result = agent(PROMPT)
    print(f"stop_reason={result.stop_reason!r}; tool body ran {TOOL_RUNS['create_ticket']} time(s)")
    show("turn 2: last message the model received", model.received[1][-1])


def model_retry_default() -> None:
    print("\n===== 5. Default model retry: the model call raises ModelThrottledException once =====")
    calls = {"n": 0}

    def script(i):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ModelThrottledException("fake throttle")
        return text_reply("ok after throttle")

    model = ScriptedModel(script)
    agent = Agent(model=model, tools=[create_ticket])  # all defaults
    # Record the delay the retry strategy asks asyncio.sleep for, instead of timing the wait,
    # so the output holds the setting and no timing. The sleep itself still runs.
    real_sleep, delays = asyncio.sleep, []

    async def recording_sleep(delay, *a, **k):
        if delay:
            delays.append(delay)
        return await real_sleep(delay, *a, **k)

    asyncio.sleep = recording_sleep
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            result = agent(PROMPT)
    finally:
        asyncio.sleep = real_sleep
    print(f"no exception; stop_reason={result.stop_reason!r}; model.stream calls={calls['n']}; "
          f"retry delay asked of asyncio.sleep before the retry succeeded: {delays} s")


def main() -> None:
    print(f"strands-agents {importlib.metadata.version('strands-agents')}")
    print(f"python {sys.version.split()[0]}")

    one_failed_call("1. Tool raises ServerValidationError (the Part 1 422), all defaults",
                    GOOD_ARGS)
    one_failed_call("2a. Arguments fail the tool's own schema: priority=123 (int for str)",
                    json.dumps({"title": "CSV export times out", "priority": 123}))
    one_failed_call("2b. Arguments fail the tool's own schema: priority missing",
                    json.dumps({"title": "CSV export times out"}))
    one_failed_call("3. Model sends unparsable JSON as the tool input",
                    '{"title": "CSV export times out", "priority": ')
    loop_forever_defaults(cap=int(os.environ.get("FOREVER_CAP", "2000")))
    model_retry_default()
    knob_limits_turns()
    knob_after_tool_hook()
    knob_hitl()


if __name__ == "__main__":
    main()
