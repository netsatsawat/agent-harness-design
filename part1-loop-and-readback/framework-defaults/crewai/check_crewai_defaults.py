"""
No-network check of what a CrewAI agent's model reads after a tool fails.

Runs CrewAI's real agent loop (Crew -> Agent -> AgentExecutor) with every agent, task, crew
and tool default left as shipped. The only custom piece is the model: a scripted fake built on
CrewAI's own extension point, crewai.llms.base_llm.BaseLLM. It records every message list the
loop sends it, so the script can print exactly what the model reads on turn 2.

CrewAI picks one of two tool loops from the model object:
  native  - the model object has supports_function_calling() returning True. Every built-in
            provider class (OpenAI, Anthropic, Gemini, Bedrock, Azure) takes this path for a
            tool-capable model, so it is the path a real team hits.
  text    - the model object has no supports_function_calling(); BaseLLM does not define it,
            so a bare custom BaseLLM falls back to the ReAct text format
            (Thought / Action / Action Input / Observation).
The script drives both.

Run from this folder with:

    python -I -u check_crewai_defaults.py < /dev/null > output.txt 2>&1

(-u keeps CrewAI's stderr lines in order with the script's stdout.)
An optional first argument, SANDBOX_DIR, receives HOME and CREWAI_STORAGE_DIR so CrewAI's
user-data files land there and nowhere else. Without it a fresh temp folder is used. The
traceback lines in the output are cut to the path inside site-packages, so they hold no local path.

Env set before CrewAI is imported (telemetry and tracing only; none of them is an agent-loop
setting): CREWAI_DISABLE_TELEMETRY, CREWAI_DISABLE_TRACKING, OTEL_SDK_DISABLED,
CREWAI_TRACING_ENABLED=false, CREWAI_DISABLE_VERSION_CHECK, DO_NOT_TRACK, LANGSMITH_TRACING.
Provider API keys are removed. Sockets are patched to refuse every connection and the script
prints any attempt at the end.
"""

from __future__ import annotations

import copy
import json
import os
import re
import socket
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------- sandbox, env, no network
SANDBOX = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="crewai-"))
for sub in ("home", "storage", "run"):
    (SANDBOX / sub).mkdir(parents=True, exist_ok=True)

for key in (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
    "AZURE_API_KEY", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "GROQ_API_KEY",
    "MISTRAL_API_KEY", "OPENROUTER_API_KEY", "CREWAI_USER_PAT", "OPENAI_BASE_URL",
    "OPENAI_API_BASE",
):
    os.environ.pop(key, None)
os.environ.update({
    "HOME": str(SANDBOX / "home"),
    "CREWAI_STORAGE_DIR": str(SANDBOX / "storage"),
    "CREWAI_DISABLE_TELEMETRY": "true",
    "CREWAI_DISABLE_TRACKING": "true",
    "OTEL_SDK_DISABLED": "true",
    "CREWAI_TRACING_ENABLED": "false",
    "CREWAI_DISABLE_VERSION_CHECK": "true",
    "DO_NOT_TRACK": "1",
    "LANGSMITH_TRACING": "false",
})
os.chdir(SANDBOX / "run")

NETWORK_ATTEMPTS: list[str] = []


def _refuse_connect(self: socket.socket, address: Any) -> None:
    NETWORK_ATTEMPTS.append(f"connect {address!r}")
    raise OSError("network disabled by check script")


def _refuse_connect_ex(self: socket.socket, address: Any) -> int:
    NETWORK_ATTEMPTS.append(f"connect_ex {address!r}")
    return 111


def _refuse_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
    NETWORK_ATTEMPTS.append(f"getaddrinfo {host!r}")
    raise socket.gaierror("network disabled by check script")


socket.socket.connect = _refuse_connect  # type: ignore[method-assign]
socket.socket.connect_ex = _refuse_connect_ex  # type: ignore[method-assign]
socket.getaddrinfo = _refuse_getaddrinfo  # type: ignore[assignment]

# ---------------------------------------------------------------- CrewAI imports
import crewai  # noqa: E402
from crewai import Agent, Crew, Task  # noqa: E402
from crewai.hooks.tool_hooks import (  # noqa: E402
    clear_all_tool_call_hooks,
    register_after_tool_call_hook,
    register_before_tool_call_hook,
)
from crewai.llms.base_llm import BaseLLM  # noqa: E402
from crewai.tools import tool  # noqa: E402
from crewai.tools.tool_failure import ToolFailure  # noqa: E402
from crewai.events import ToolUsageErrorEvent, crewai_event_bus  # noqa: E402
from pydantic import PrivateAttr  # noqa: E402

# Observation only: count the framework's own "tool raised" events per scenario.
TOOL_ERROR_EVENTS: list[str] = []


@crewai_event_bus.on(ToolUsageErrorEvent)
def _count_tool_errors(source: Any, event: Any) -> None:
    TOOL_ERROR_EVENTS.append(type(source).__name__)


# ---------------------------------------------------------------- copied from Part 1
# Verbatim from agent-harness-design/part1-loop-and-readback/experiment/servers.py
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


# ---------------------------------------------------------------- the tool (CrewAI @tool)
TOOL_RUNS: list[dict[str, Any]] = []


@tool("create_ticket")
def create_ticket(title: str, priority: str) -> str:
    """Create a support ticket.

    Args:
        title: Short summary of the issue.
        priority: Priority for the ticket.
    """
    TOOL_RUNS.append({"title": title, "priority": priority})
    return json.dumps(ticket_server(title, priority))


# ---------------------------------------------------------------- scripted fake models
class _RecordingLLM(BaseLLM):
    """Records each call and asks a responder function what to return."""

    _responder: Any = PrivateAttr(default=None)
    _calls: list = PrivateAttr(default_factory=list)

    def __init__(self, responder: Any, **kwargs: Any) -> None:
        super().__init__(model="scripted-fake", **kwargs)
        self._responder = responder

    def call(self, messages, tools=None, callbacks=None, available_functions=None,
             from_task=None, from_agent=None, response_model=None):
        snap = ([{"role": "user", "content": messages}] if isinstance(messages, str)
                else copy.deepcopy(list(messages)))
        tool_names = [t["function"]["name"] for t in tools] if tools else None
        self._calls.append({"messages": snap, "tool_names": tool_names})
        return self._responder(len(self._calls), snap, tools)

    def get_context_window_size(self) -> int:
        return 128_000

    def get_input_tokens_count(self, messages, tools=None, response_model=None) -> int:
        # Same four-characters-per-token estimate as BaseLLM, minus its per-call warning.
        text = messages if isinstance(messages, str) else json.dumps(messages, default=str)
        return (len(text) + 3) // 4


class NativeFakeLLM(_RecordingLLM):
    """Same shape as CrewAI's built-in providers: native function calling on."""

    def supports_function_calling(self) -> bool:
        return True


class TextFakeLLM(_RecordingLLM):
    """A bare BaseLLM subclass: no supports_function_calling, so CrewAI uses ReAct text."""


def native_call(args: dict[str, Any] | str, call_id: str = "call_1") -> list[dict[str, Any]]:
    arguments = args if isinstance(args, str) else json.dumps(args)
    return [{"id": call_id, "type": "function",
             "function": {"name": "create_ticket", "arguments": arguments}}]


def text_call(args: dict[str, Any]) -> str:
    return ("Thought: I should file the ticket.\nAction: create_ticket\n"
            f"Action Input: {json.dumps(args)}")


FINAL_TEXT = "Thought: I now know the final answer\nFinal Answer: done"
HIGH = {"title": "CSV export times out", "priority": "high"}


# ---------------------------------------------------------------- run helpers
def build_crew(llm: BaseLLM, tools: list | None = None) -> Crew:
    agent = Agent(
        role="Support agent",
        goal="File support tickets",
        backstory="You file support tickets for the team.",
        llm=llm,
        tools=tools if tools is not None else [create_ticket],
    )
    task = Task(
        description="File a high-priority ticket: CSV export times out.",
        expected_output="The ticket id.",
        agent=agent,
    )
    return Crew(agents=[agent], tasks=[task])


def _no_local_path(line: str) -> str:
    """Cut a traceback path to its part inside site-packages, or to the file name."""
    line = re.sub(r'"[^"]*?site-packages/', '"', line)
    return re.sub(r'"/[^"]*/([^/"]+\.py)"', r'"\1"', line)


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=repr)


def run(name: str, llm: _RecordingLLM, tools: list | None = None,
        show_turn: int = 2) -> None:
    print("\n" + "=" * 90)
    print(f"SCENARIO {name}")
    print("=" * 90)
    TOOL_RUNS.clear()
    TOOL_ERROR_EVENTS.clear()
    crew = build_crew(llm, tools)
    agent = crew.agents[0]
    print(f"agent.max_iter={agent.max_iter} max_rpm={agent.max_rpm} "
          f"max_execution_time={agent.max_execution_time} "
          f"max_retry_limit={agent.max_retry_limit} max_tokens={agent.max_tokens} "
          f"tool_failure_policy={agent.tool_failure_policy} "
          f"task.human_input={crew.tasks[0].human_input} "
          f"tool.max_usage_count={create_ticket.max_usage_count}")
    outcome: dict[str, Any] = {}
    try:
        out = crew.kickoff()
        outcome["returned"] = True
        outcome["raw"] = out.raw
        outcome["tool_failures"] = [
            {"tool": r.tool_name, "reason": r.failure.reason.value, "code": r.failure.code,
             "message": r.failure.message} for r in out.tool_failures
        ]
    except BaseException as exc:  # noqa: BLE001
        outcome["returned"] = False
        outcome["exception_type"] = f"{type(exc).__module__}.{type(exc).__name__}"
        outcome["exception_message"] = str(exc)
        outcome["traceback_tail"] = [_no_local_path(x) for x in
                                     traceback.format_exc().strip().splitlines()[-3:]]

    crewai_event_bus.flush()
    calls = llm._calls
    print(f"LLM calls made: {len(calls)}")
    print(f"tool body runs: {len(TOOL_RUNS)} {TOOL_RUNS[:3]}{' ...' if len(TOOL_RUNS) > 3 else ''}")
    print(f"ToolUsageErrorEvent count: {len(TOOL_ERROR_EVENTS)} (emitted by {sorted(set(TOOL_ERROR_EVENTS))})")
    if len(calls) >= show_turn:
        before = calls[show_turn - 2]["messages"]
        after = calls[show_turn - 1]["messages"]
        new = after[len(before):]
        print(f"--- messages added between call {show_turn - 1} and call {show_turn} "
              f"(what the model reads after its tool call), full dicts:")
        print(dump(new))
    else:
        print(f"--- no call {show_turn}: the run ended before the model was called again")
    print("--- outcome returned to the caller:")
    print(dump(outcome))


def run_limit(name: str, llm: _RecordingLLM) -> None:
    run(name, llm, show_turn=2)
    calls = llm._calls
    if calls:
        last = calls[-1]
        print(f"--- last LLM call: tools passed = {last['tool_names']}")
        print("--- last message in the last LLM call:")
        print(dump(last["messages"][-1]))


# ---------------------------------------------------------------- scenarios
def main() -> None:
    print(f"crewai {crewai.__version__}  python {sys.version.split()[0]}")

    # 1. Tool raises ServerValidationError, native function calling (built-in provider path)
    def r1(n, msgs, tools):
        return native_call(HIGH) if n == 1 else "TCK done"
    run("1 native: tool raises ServerValidationError", NativeFakeLLM(r1))

    # 2. Same failure, ReAct text path (bare BaseLLM)
    def r2(n, msgs, tools):
        return text_call(HIGH) if n == 1 else FINAL_TEXT
    run("2 text/ReAct: tool raises ServerValidationError", TextFakeLLM(r2))

    # 3. Arguments fail the tool's own schema (priority is an int), native path
    def r3(n, msgs, tools):
        return native_call({"title": "CSV export times out", "priority": 123}) if n == 1 \
            else "done"
    run("3 native: bad args priority=123", NativeFakeLLM(r3))

    # 4. Missing required argument, native path
    def r4(n, msgs, tools):
        return native_call({"title": "CSV export times out"}) if n == 1 else "done"
    run("4 native: missing argument priority", NativeFakeLLM(r4))

    # 5. Arguments that are not JSON at all, native path
    def r5(n, msgs, tools):
        return native_call('{"title": "CSV export times out", "priority": ') if n == 1 \
            else "done"
    run("5 native: arguments are broken JSON", NativeFakeLLM(r5))

    # 6. Bad args on the ReAct text path
    def r6(n, msgs, tools):
        return text_call({"title": "CSV export times out", "priority": 123}) if n == 1 \
            else FINAL_TEXT
    run("6 text/ReAct: bad args priority=123", TextFakeLLM(r6))

    # 7. Default turn limit: the model calls a working tool forever with new args each time
    def r7(n, msgs, tools):
        if tools is None:
            return "Forced final answer from the fake model."
        return native_call({"title": f"attempt {n}", "priority": "P1"}, call_id=f"call_{n}")
    run_limit("7 native: model calls the tool forever (default max_iter)", NativeFakeLLM(r7))

    # 8. The model repeats the identical failing call forever
    def r8(n, msgs, tools):
        if tools is None:
            return "Forced final answer from the fake model."
        return native_call(HIGH, call_id=f"call_{n}")
    run_limit("8 native: model repeats the identical failing call forever", NativeFakeLLM(r8))

    # ------------------------------------------------------------ knobs (NOT defaults)
    print("\n" + "#" * 90)
    print("# KNOB DEMOS BELOW: each changes one setting on purpose; they are not defaults")
    print("#" * 90)

    # K1. Global or per-tool-name after_tool_call hook rewrites what the model reads
    def note_hook(ctx):
        if ctx.tool_name == "create_ticket" and str(ctx.tool_result).startswith(
                ("Error executing tool:", "\nI encountered an error")):
            return ("create_ticket failed: priority must be one of P0 (critical), "
                    "P1 (high), P2 (normal). Retry with one of those codes.")
        return None

    register_after_tool_call_hook(note_hook)
    try:
        run("K1 native + after_tool_call hook: tool raises", NativeFakeLLM(r1))
    finally:
        clear_all_tool_call_hooks()

    # K2. The tool returns CrewAI's ToolFailure instead of raising (per-tool choice)
    @tool("create_ticket")
    def create_ticket_reports(title: str, priority: str) -> Any:
        """Create a support ticket.

        Args:
            title: Short summary of the issue.
            priority: Priority for the ticket.
        """
        TOOL_RUNS.append({"title": title, "priority": priority})
        try:
            return json.dumps(ticket_server(title, priority))
        except ServerValidationError:
            return ToolFailure(message="priority must be P0, P1 or P2", code="enum")

    run("K2 native + tool returns ToolFailure", NativeFakeLLM(r1),
        tools=[create_ticket_reports])

    # K3. Approval gate: a before_tool_call hook that says no (stands in for a human "no")
    def deny_hook(ctx):
        return False if ctx.tool_name == "create_ticket" else None

    register_before_tool_call_hook(deny_hook)
    try:
        run("K3 native + before_tool_call hook returns False", NativeFakeLLM(r1))
    finally:
        clear_all_tool_call_hooks()

    print("\n" + "=" * 90)
    print(f"network attempts blocked: {len(NETWORK_ATTEMPTS)} {NETWORK_ATTEMPTS[:5]}")


if __name__ == "__main__":
    main()
