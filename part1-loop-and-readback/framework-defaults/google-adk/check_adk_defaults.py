"""
What does a Google ADK (google-adk 2.13.0) agent read after a tool raises, with every
default left alone?

No network, no API key, no model call. A scripted fake model (a subclass of
google.adk.models.BaseLlm, ADK's own extension point for custom models) drives the real
LlmAgent loop through InMemoryRunner. The fake model records every LlmRequest it gets, so
the script prints exactly what the model would read on turn 2.

Run from this folder with:

    python -I check_adk_defaults.py > output.txt

ADK logs the tracebacks of the failed runs to stderr. output.txt holds stdout only.
"""

from __future__ import annotations

import os

# Environment hygiene, set before ADK is imported. No provider keys, no telemetry.
for _key in list(os.environ):
    if (
        _key in (
            "GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI",
            "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GOOGLE_APPLICATION_CREDENTIALS",
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ADK_MAX_LLM_CALLS",
        )
        or _key.startswith("ADK_ENABLE_")
        or _key.startswith("ADK_DISABLE_")
    ):
        del os.environ[_key]
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["DO_NOT_TRACK"] = "1"
os.environ["LANGSMITH_TRACING"] = "false"

# Network guard: any outbound connect is recorded and refused, so the run proves it is
# offline. The count is printed at the end.
import socket

NET_ATTEMPTS: list = []


def _refuse(self, address, *a, **k):
    NET_ATTEMPTS.append(repr(address))
    raise OSError(f"network blocked by check script: {address!r}")


socket.socket.connect = _refuse
socket.socket.connect_ex = _refuse

import asyncio
import json
import re
from typing import Any, Callable

from google.adk.agents import LlmAgent
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.run_config import RunConfig
from google.adk.features import FeatureName, is_feature_enabled, override_feature_enabled
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.plugins.reflect_retry_tool_plugin import ReflectAndRetryToolPlugin
from google.adk.runners import InMemoryRunner
from google.adk.tools import FunctionTool
from google.adk.version import __version__ as ADK_VERSION
from google.genai import types

# ---------------------------------------------------------------------------------------
# Copied verbatim from agent-harness-design/part1-loop-and-readback/experiment/servers.py
# ---------------------------------------------------------------------------------------
E164_PATTERN = r"^\+[1-9]\d{1,14}$"


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
# ---------------------------------------------------------------------------------------


TOOL_CALLS: list = []  # every time create_ticket's body actually runs


def create_ticket(title: str, priority: str) -> dict:
    """Create a support ticket.

    Args:
      title: Short summary of the problem.
      priority: The ticket priority.
    """
    TOOL_CALLS.append({"title": title, "priority": priority})
    return ticket_server(title, priority)


def ping() -> dict:
    """Health check that always succeeds."""
    return {"ok": True}


# ---------------------------------------------------------------------------------------
# Scripted fake model built on ADK's own BaseLlm extension point.
# ---------------------------------------------------------------------------------------
def call(name: str, args: dict) -> LlmResponse:
    return LlmResponse(content=types.Content(
        role="model", parts=[types.Part(function_call=types.FunctionCall(name=name, args=args))]
    ))


def say(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


class ScriptedLlm(BaseLlm):
    """Plays back one response per turn and records every request it receives."""

    model: str = "scripted-fake-model"
    turns: list[Any] = []          # each: LlmResponse, or callable(turn_index) -> LlmResponse
    requests: list[Any] = []       # the LlmRequest seen on each turn (deep copies)

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False):
        i = len(self.requests)
        self.requests.append(llm_request.model_copy(deep=True))
        nxt = self.turns[min(i, len(self.turns) - 1)]
        yield nxt(i) if callable(nxt) else nxt


def dump_content(content: types.Content) -> dict:
    return content.model_dump(mode="json", exclude_none=True)


async def run(agent: LlmAgent, *, plugins: list | None = None,
              run_config: RunConfig | None = None) -> dict:
    TOOL_CALLS.clear()
    runner = InMemoryRunner(agent=agent, app_name="check", plugins=plugins)
    session = await runner.session_service.create_session(app_name="check", user_id="u1")
    msg = types.Content(role="user", parts=[types.Part(text="File a high-priority ticket.")])
    events, exc = [], None
    kwargs = {"user_id": "u1", "session_id": session.id, "new_message": msg}
    if run_config is not None:
        kwargs["run_config"] = run_config
    try:
        async for ev in runner.run_async(**kwargs):
            events.append(ev)
    except BaseException as e:  # noqa: BLE001 - we want to record whatever escapes
        exc = e
    finally:
        await runner.close()
    return {"events": events, "exc": exc, "model": agent.model,
            "tool_runs": len(TOOL_CALLS)}


def report(title: str, result: dict, *, show_turn2: bool = True) -> None:
    model: ScriptedLlm = result["model"]
    print("=" * 88)
    print(title)
    print("-" * 88)
    print(f"model turns made: {len(model.requests)}")
    print(f"create_ticket body executions: {result['tool_runs']}")
    if result["exc"] is not None:
        e = result["exc"]
        print(f"run stopped with exception: {type(e).__module__}.{type(e).__name__}")
        print(f"exception message: {e}")
    else:
        print("run ended normally (no exception reached the caller)")
    if show_turn2:
        if len(model.requests) >= 2:
            last = model.requests[1].contents[-1]
            print("what the model receives on turn 2 (last content of the request):")
            print(json.dumps(dump_content(last), indent=2, ensure_ascii=False))
            for part in last.parts or []:
                if part.function_response is not None:
                    print("verbatim response dict:", repr(part.function_response.response))
        else:
            print("turn 2 never happened: the model received nothing after the failure")
    print()


def new_model(turns: list) -> ScriptedLlm:
    return ScriptedLlm(turns=turns, requests=[])


HIGH = {"title": "CSV export times out", "priority": "high"}


async def main() -> None:
    print(f"google-adk version: {ADK_VERSION}")
    print(f"RunConfig().max_llm_calls default: {RunConfig().max_llm_calls}")
    print(f"LlmAgent.on_tool_error_callback default: "
          f"{LlmAgent.model_fields['on_tool_error_callback'].default!r}")
    print(f"FunctionTool(create_ticket)._require_confirmation default: "
          f"{FunctionTool(create_ticket)._require_confirmation!r}")
    print(f"FUNCTION_TOOL_ARG_VALIDATION enabled by default: "
          f"{is_feature_enabled(FeatureName.FUNCTION_TOOL_ARG_VALIDATION)}")
    print(f"InMemoryRunner default plugins: "
          f"{InMemoryRunner(agent=LlmAgent(name='x', model=new_model([say('hi')])), app_name='check').plugin_manager.plugins!r}")
    print()

    # 1. F1: all defaults, the tool raises ServerValidationError for priority "high".
    m = new_model([call("create_ticket", HIGH), say("done")])
    r = await run(LlmAgent(name="support", model=m, tools=[create_ticket]))
    report("[1] DEFAULTS: tool raises ServerValidationError (priority='high')", r)

    # 2. F1b: a mandatory argument is missing (FunctionTool's own check).
    m = new_model([call("create_ticket", {"title": "CSV export times out"}), say("done")])
    r = await run(LlmAgent(name="support", model=m, tools=[create_ticket]))
    report("[2] DEFAULTS: missing mandatory argument 'priority'", r)

    # 3. F1b: wrong argument type, priority=123. Arg type validation is off by default,
    #    so the function runs with 123 and the server raises.
    m = new_model([call("create_ticket", {"title": "CSV export times out", "priority": 123}),
                   say("done")])
    r = await run(LlmAgent(name="support", model=m, tools=[create_ticket]))
    report("[3] DEFAULTS: wrong argument type priority=123", r)

    # 4. Opt-in, NOT a default: the experimental FUNCTION_TOOL_ARG_VALIDATION flag.
    override_feature_enabled(FeatureName.FUNCTION_TOOL_ARG_VALIDATION, True)
    try:
        m = new_model([call("create_ticket", {"title": "CSV export times out", "priority": 123}),
                       say("done")])
        r = await run(LlmAgent(name="support", model=m, tools=[create_ticket]))
        report("[4] OPT-IN ADK_ENABLE_FUNCTION_TOOL_ARG_VALIDATION: priority=123", r)
    finally:
        override_feature_enabled(FeatureName.FUNCTION_TOOL_ARG_VALIDATION, False)

    # 5. F2 per agent: LlmAgent(on_tool_error_callback=...) writes the team's own note.
    def team_note(tool, args, tool_context, error):
        return {"error": f"{tool.name} failed: {error}"}

    m = new_model([call("create_ticket", HIGH), say("done")])
    r = await run(LlmAgent(name="support", model=m, tools=[create_ticket],
                           on_tool_error_callback=team_note))
    report("[5] KNOB LlmAgent(on_tool_error_callback=team_note), priority='high'", r)

    # 6. F2 global: a runner plugin's on_tool_error_callback.
    class TeamNotePlugin(BasePlugin):
        async def on_tool_error_callback(self, *, tool, tool_args, tool_context, error):
            return {"error": f"{tool.name} failed: {error}"}

    m = new_model([call("create_ticket", HIGH), say("done")])
    r = await run(LlmAgent(name="support", model=m, tools=[create_ticket]),
                  plugins=[TeamNotePlugin(name="team_note")])
    report("[6] KNOB plugin on_tool_error_callback (runner-wide), priority='high'", r)

    # 7. F6 opt-in: the built-in ReflectAndRetryToolPlugin with its own defaults
    #    (max_retries=3). Not installed unless the team adds it.
    m = new_model([call("create_ticket", HIGH)])  # keeps sending the same bad call
    r = await run(LlmAgent(name="support", model=m, tools=[create_ticket]),
                  plugins=[ReflectAndRetryToolPlugin()])
    report("[7] OPT-IN ReflectAndRetryToolPlugin() defaults, same bad call every turn", r)

    # 8. F5 opt-in: FunctionTool(require_confirmation=True). Default is False.
    m = new_model([call("create_ticket", {"title": "CSV export times out", "priority": "P1"}),
                   say("done")])
    r = await run(LlmAgent(name="support", model=m,
                           tools=[FunctionTool(create_ticket, require_confirmation=True)]))
    report("[8] OPT-IN FunctionTool(create_ticket, require_confirmation=True), valid call", r,
           show_turn2=False)
    for ev in r["events"]:
        for part in (ev.content.parts if ev.content else []) or []:
            if part.function_call is not None:
                print(f"  event author={ev.author} function_call name={part.function_call.name}"
                      f" args={json.dumps(part.function_call.args, default=str)[:300]}")
            if part.function_response is not None:
                print(f"  event author={ev.author} function_response "
                      f"name={part.function_response.name} "
                      f"response={part.function_response.response!r}")
    print()

    # 9. F3: default max_llm_calls. The fake model calls ping() forever.
    m = new_model([call("ping", {})])
    r = await run(LlmAgent(name="looper", model=m, tools=[ping]))
    report("[9] DEFAULTS: model calls a working tool forever (no run_config passed)", r,
           show_turn2=False)
    print(f"  events yielded before the stop: {len(r['events'])}")
    print(f"  exception is LlmCallsLimitExceededError: "
          f"{isinstance(r['exc'], LlmCallsLimitExceededError)}")
    print()
    print(f"outbound network connect attempts during the whole run: {len(NET_ATTEMPTS)}")


if __name__ == "__main__":
    asyncio.run(main())
