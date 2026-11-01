"""
What the model reads after a failed tool call in the OpenAI Agents SDK, with defaults.

Runs the REAL Runner loop (agents.Runner.run) with every default left alone: no max_turns,
no run_config, no error_handlers, and a @function_tool with no failure_error_function and no
needs_approval.

The model is a scripted stand-in built on the SDK's own extension point: a subclass of
agents.models.interface.Model. It records the instructions and the input item list the runner
hands it on every turn, so "what the model reads on turn 2" is captured from the loop itself,
not reconstructed. (The SDK also ships agents.testing.ScriptedModel; it is not used here.)

No network: provider keys are removed, OPENAI_AGENTS_DISABLE_TRACING=1, and every socket
connect and DNS lookup is blocked (the script reports how many were attempted). Run from this
folder with:

    python -I -u check_openai_agents_defaults.py > output.txt

The script prints no paths and no timings.
"""

from __future__ import annotations

import os

for _k in list(os.environ):
    if _k.endswith("_API_KEY") or _k.startswith(("OPENAI_", "OTEL_")):
        os.environ.pop(_k)
os.environ.update({
    "OPENAI_AGENTS_DISABLE_TRACING": "1",  # read once by the trace provider; no trace upload
    "OTEL_SDK_DISABLED": "true",
    "DO_NOT_TRACK": "1",
})

import socket  # noqa: E402

BLOCKED: list[str] = []


def _blocked(*a, **k):
    BLOCKED.append(repr(a[:2]))
    raise OSError("network blocked by check script")


socket.socket.connect = _blocked  # type: ignore[assignment]
socket.socket.connect_ex = _blocked  # type: ignore[assignment]
socket.create_connection = _blocked  # type: ignore[assignment]
socket.getaddrinfo = _blocked  # type: ignore[assignment]

import ast  # noqa: E402
import asyncio  # noqa: E402
import copy  # noqa: E402
import dataclasses  # noqa: E402
import inspect  # noqa: E402
import json  # noqa: E402
from importlib.metadata import version  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Callable  # noqa: E402

from openai.types.responses import (  # noqa: E402
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

import agents  # noqa: E402
from agents import Agent, ModelSettings, RunConfig, Runner, function_tool  # noqa: E402
from agents.items import ItemHelpers, MessageOutputItem, ModelResponse  # noqa: E402
from agents.models.interface import Model  # noqa: E402
from agents.run_config import DEFAULT_MAX_TURNS  # noqa: E402
from agents.usage import Usage  # noqa: E402


# ---- copied verbatim from experiment/servers.py (checked at run time, see verbatim_check) ----
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

TOOL_RUNS = {"create_ticket": 0, "ping": 0}


def create_ticket(title: str, priority: str) -> dict:
    """Create a support ticket.

    Args:
        title: Short summary of the issue.
        priority: Priority for the ticket.
    """
    TOOL_RUNS["create_ticket"] += 1
    return ticket_server(title, priority)


# DEFAULTS: function_tool(f) with no keyword arguments, the same as a bare @function_tool.
# The plain function stays importable so the NON-DEFAULT sections can wrap it again with one knob.
create_ticket_tool = function_tool(create_ticket)


@function_tool
def ping() -> str:
    """Harmless tool for the turn-limit test."""
    TOOL_RUNS["ping"] += 1
    return "pong"


# ---- scripted stand-in model ------------------------------------------------------------------
def call(name: str, arguments: str, call_id: str) -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall(
        id=f"fc_{call_id}", call_id=call_id, type="function_call", name=name,
        arguments=arguments,
    )


def text(t: str) -> ResponseOutputMessage:
    return ResponseOutputMessage(
        id="msg_1", type="message", role="assistant", status="completed",
        content=[ResponseOutputText(type="output_text", text=t, annotations=[], logprobs=[])],
    )


class ScriptedModel(Model):
    """Answers from a script; records what each turn was handed."""

    def __init__(self, responder: Callable[[int], list], usage_per_call: Usage | None = None,
                 keep: bool = True):
        self.responder, self.keep = responder, keep
        self.usage_per_call = usage_per_call
        self.seen: list[dict] = []
        self.count = 0

    async def get_response(self, system_instructions, input, model_settings, tools,
                           output_schema, handoffs, tracing, *, previous_response_id,
                           conversation_id, prompt) -> ModelResponse:
        turn = self.count
        self.count += 1
        if self.keep:
            self.seen.append({
                "system_instructions": system_instructions,
                "input": copy.deepcopy(input),
                "tools": [t.name for t in tools],
            })
        u = copy.deepcopy(self.usage_per_call) if self.usage_per_call else Usage(requests=1)
        return ModelResponse(output=self.responder(turn), usage=u, response_id=None)

    async def stream_response(self, *a, **k):  # not used: the script only calls Runner.run
        raise NotImplementedError("stream_response is not used by this check")
        yield  # pragma: no cover


def script(*turns: list) -> Callable[[int], list]:
    def r(turn: int) -> list:
        return turns[turn] if turn < len(turns) else [text("(script ended)")]
    return r


USER = "File a high-priority ticket: CSV export times out"
BIG_USAGE = Usage(requests=1, input_tokens=1_000_000, output_tokens=1_000,
                  total_tokens=1_001_000)


def tool_outputs(turn_input: Any) -> list[dict]:
    if isinstance(turn_input, str):
        return []
    return [it for it in turn_input if isinstance(it, dict)
            and it.get("type") == "function_call_output"]


def show_turn2(model: ScriptedModel) -> None:
    if model.count < 2:
        print("    turn 2: NEVER HAPPENED (the model was not called again)")
        return
    t2 = model.seen[1]
    kinds = [it.get("type", it.get("role")) if isinstance(it, dict) else type(it).__name__
             for it in t2["input"]]
    print(f"    turn 2: system_instructions={t2['system_instructions']!r}")
    print(f"    turn 2: input item types, in order: {kinds}")
    print("    turn 2: model received this tool-result item:")
    for it in tool_outputs(t2["input"]):
        print("      " + json.dumps(it, ensure_ascii=False))
        print("      output, printed raw:")
        for line in str(it.get("output")).split("\n"):
            print("        | " + line)


def run(agent: Agent, inp: Any = USER, **non_default: Any):
    return asyncio.run(Runner.run(agent, inp, **non_default))


def run_once(label: str, first_turn: list, tool=None, **non_default: Any) -> Any:
    print(f"\n=== {label}")
    TOOL_RUNS["create_ticket"] = 0
    model = ScriptedModel(script(first_turn, [text("Ticket handled.")]))
    agent = Agent(name="ops", model=model, tools=[tool or create_ticket_tool])
    c = first_turn[0]
    print(f"    turn 1 tool call: {c.name}({c.arguments})")
    result = None
    try:
        result = run(agent, **non_default)
        print("    run outcome: RETURNED to caller (no exception)")
        print(f"    final_output: {result.final_output!r}")
        print(f"    interruptions (pending approvals): {len(result.interruptions)}")
    except Exception as e:  # noqa: BLE001
        print("    run outcome: EXCEPTION propagated to caller")
        print(f"    exception type: {type(e).__module__}.{type(e).__qualname__}")
        print(f"    exception str : {str(e)}")
        if e.__cause__ is not None:
            print(f"    __cause__     : {type(e.__cause__).__qualname__}: {e.__cause__}")
    print(f"    tool function executions: {TOOL_RUNS['create_ticket']}")
    print(f"    model calls made: {model.count}")
    show_turn2(model)
    return result


def run_loop(label: str, usage_per_call: Usage | None = None, **non_default: Any) -> None:
    print(f"\n=== {label}")
    TOOL_RUNS["ping"] = 0
    model = ScriptedModel(lambda t: [call("ping", "{}", f"call_{t}")],
                          usage_per_call=usage_per_call, keep=False)
    agent = Agent(name="ops", model=model, tools=[ping])
    try:
        result = run(agent, **non_default)
        print("    run outcome: RETURNED to caller (no exception)")
        print(f"    final_output: {result.final_output!r}")
        last = result.new_items[-1] if result.new_items else None
        if last is not None:
            body = (ItemHelpers.text_message_output(last)
                    if isinstance(last, MessageOutputItem) else type(last.raw_item).__name__)
            print(f"    last new_item: {type(last).__name__} {body!r}")
        u = result.context_wrapper.usage
        print(f"    usage seen by the run: requests={u.requests} input_tokens={u.input_tokens}"
              f" output_tokens={u.output_tokens}")
    except Exception as e:  # noqa: BLE001
        print("    run outcome: EXCEPTION propagated to caller")
        print(f"    exception type: {type(e).__module__}.{type(e).__qualname__}")
        print(f"    exception str : {str(e)}")
        rd = getattr(e, "run_data", None)
        if rd is not None:
            u = rd.context_wrapper.usage
            print(f"    usage on the exception's run_data: requests={u.requests}"
                  f" input_tokens={u.input_tokens} output_tokens={u.output_tokens}")
    print(f"    model calls made: {model.count}   ping executions: {TOOL_RUNS['ping']}")


def verbatim_check() -> None:
    """Compare the copied server code with experiment/servers.py, if it is where we expect."""
    here = Path(__file__).resolve()
    servers = here.parents[2] / "experiment" / "servers.py"
    rel = "../../experiment/servers.py"
    if not servers.exists():
        print(f"verbatim copy check: {rel} not found, skipped")
        return

    def segments(src: str) -> dict[str, str]:
        tree = ast.parse(src)
        return {n.name: ast.get_source_segment(src, n) for n in tree.body
                if isinstance(n, (ast.ClassDef, ast.FunctionDef))
                and n.name in ("ServerValidationError", "ticket_server")}

    a, b = segments(servers.read_text()), segments(here.read_text())
    same = a == b and len(a) == 2
    print(f"verbatim copy check vs {rel}: ServerValidationError + ticket_server "
          f"{'MATCH' if same else 'DIFFER'}")


def main() -> None:
    for p in ("openai-agents", "openai", "pydantic"):
        print(f"{p}=={version(p)}")
    verbatim_check()
    print(f"DEFAULT_MAX_TURNS = {DEFAULT_MAX_TURNS}")
    sig = inspect.signature(Runner.run)
    print(f"Runner.run defaults: max_turns={sig.parameters['max_turns'].default!r}, "
          f"run_config={sig.parameters['run_config'].default!r}, "
          f"error_handlers={sig.parameters['error_handlers'].default!r}")
    rc = RunConfig()
    print(f"RunConfig() defaults: tool_error_formatter={rc.tool_error_formatter!r}, "
          f"tool_not_found_behavior={rc.tool_not_found_behavior!r}, "
          f"tracing_disabled={rc.tracing_disabled!r}")
    ms = ModelSettings()
    print(f"ModelSettings() defaults: retry={ms.retry!r}, max_tokens={ms.max_tokens!r}, "
          f"timeout={ms.timeout!r}")
    print(f"create_ticket FunctionTool: needs_approval={create_ticket_tool.needs_approval!r}, "
          f"strict_json_schema={create_ticket_tool.strict_json_schema!r}, "
          f"timeout_seconds={create_ticket_tool.timeout_seconds!r}")
    print("create_ticket params_json_schema: "
          f"{json.dumps(create_ticket_tool.params_json_schema)}")
    words = ("budget", "cost", "token", "usage", "request", "retry", "retries")
    hits = sorted(f.name for f in dataclasses.fields(RunConfig)
                  if any(w in f.name for w in words))
    rhits = sorted(n for n in sig.parameters if any(w in n for w in words))
    print(f"RunConfig fields named like a budget/limit/retry ({'/'.join(words)}): {hits}")
    print(f"Runner.run parameters named like a budget/limit/retry: {rhits}")

    print("\n##### DEFAULTS UNTOUCHED #####")
    print("    Agent(name='ops', model=<stand-in>, tools=[function_tool(create_ticket)])")
    print("    Runner.run(agent, USER)  # no max_turns, run_config, error_handlers or hooks")
    high = [call("create_ticket",
                 json.dumps({"title": "CSV export times out", "priority": "high"}), "call_1")]
    run_once("F1 tool raises ServerValidationError (priority='high')", high)

    bad_type = [call("create_ticket",
                     json.dumps({"title": "CSV export times out", "priority": 123}), "call_1")]
    missing = [call("create_ticket", json.dumps({"title": "CSV export times out"}), "call_1")]
    broken = [call("create_ticket", '{"title": "CSV export times out", "priority": ', "call_1")]
    run_once("F1b bad args: priority=123 (fails the tool's own schema)", bad_type)
    run_once("F1b bad args: priority missing", missing)
    run_once("F1b bad args: unparsable JSON", broken)

    unknown = [call("create_tickets",
                    json.dumps({"title": "CSV export times out", "priority": "P1"}), "call_1")]
    run_once("F1c (extra) model calls a tool name that does not exist ('create_tickets')",
             unknown)

    run_loop("F3+F4 turn limit and budget: model calls ping() forever, every default; the"
             " stand-in reports 1,000,000 input tokens per call",
             usage_per_call=BIG_USAGE)

    print("\n    F6 retry: see the F1 row. The tool body ran once; the SDK called the model again"
          "\n    with the error line, and nothing in the SDK called the tool a second time.")

    print("\n##### NON-DEFAULT, for F2 only: the knobs that replace the text #####")

    def team_note(ctx: Any, error: Exception) -> str:
        return ("create_ticket failed: priority must be one of P0 (critical), "
                "P1 (high), P2 (normal). Map the user's word to a code and call again.")

    noted = function_tool(create_ticket, failure_error_function=team_note)
    run_once("F2a knob: function_tool(failure_error_function=team_note), per tool", high,
             tool=noted)

    seen_args: list[dict] = []

    def formatter(args: Any) -> str | None:
        seen_args.append({"kind": args.kind, "tool_type": args.tool_type,
                          "tool_name": args.tool_name, "call_id": args.call_id,
                          "default_message": args.default_message,
                          "error": f"{type(args.error).__qualname__}: {args.error}"})
        if isinstance(args.error, ServerValidationError):
            return (f"The ticket service rejected {args.error.field_name}="
                    f"{args.error.value!r}. Allowed values: P0 (critical), P1 (high), "
                    "P2 (normal).")
        return None  # fall back to the SDK default line

    for label, turn in (("on the 422", high), ("on priority=123 (schema failure)", bad_type)):
        seen_args.clear()
        run_once(f"F2b knob: RunConfig(tool_error_formatter=formatter), run-wide, {label}",
                 turn, run_config=RunConfig(tool_error_formatter=formatter))
        print(f"    formatter was called with: {json.dumps(seen_args, ensure_ascii=False)}")

    seen_args.clear()
    run_once("F2b precedence: per-tool failure_error_function AND run-wide tool_error_formatter",
             high, tool=noted, run_config=RunConfig(tool_error_formatter=formatter))
    print(f"    formatter was called {len(seen_args)} time(s)")

    raising = function_tool(create_ticket, failure_error_function=None)
    run_once("F2c knob: function_tool(failure_error_function=None), errors propagate", high,
             tool=raising)

    print("\n##### NON-DEFAULT, for F3 only: error_handlers turns MaxTurnsExceeded into output"
          " #####")
    from agents import RunErrorHandlerResult

    handler_saw: list[str] = []

    def on_max_turns(data: Any) -> RunErrorHandlerResult:
        handler_saw.append(f"error={type(data.error).__qualname__}: {data.error}; "
                           f"run_data.new_items={len(data.run_data.new_items)}; "
                           f"raw_responses={len(data.run_data.raw_responses)}")
        return RunErrorHandlerResult(
            final_output="Stopped after the turn limit. The ticket was not filed.")

    run_loop("F3 knob: Runner.run(..., error_handlers={'max_turns': on_max_turns})",
             usage_per_call=BIG_USAGE, error_handlers={"max_turns": on_max_turns})
    print(f"    handler saw: {handler_saw}")

    print("\n##### NON-DEFAULT, for F5 only: needs_approval=True #####")
    gated = function_tool(create_ticket, needs_approval=True)
    ok = [call("create_ticket",
               json.dumps({"title": "CSV export times out", "priority": "P1"}), "call_1")]
    TOOL_RUNS["create_ticket"] = 0
    model = ScriptedModel(script(ok, [text("Ticket handled.")]))
    agent = Agent(name="ops", model=model, tools=[gated])
    print("\n=== F5 knob: function_tool(needs_approval=True), valid call priority='P1'")
    result = run(agent)
    print(f"    run outcome: RETURNED; final_output={result.final_output!r}; "
          f"interruptions={[(type(i).__name__, i.name) for i in result.interruptions]}")
    print(f"    tool function executions: {TOOL_RUNS['create_ticket']}   "
          f"model calls made: {model.count}")
    state = result.to_state()
    state.reject(result.interruptions[0])
    result2 = run(agent, state)
    print("    after state.reject(...) and Runner.run(agent, state):")
    print(f"    final_output={result2.final_output!r}; tool function executions: "
          f"{TOOL_RUNS['create_ticket']}; model calls made: {model.count}")
    show_turn2(model)

    print(f"\nsocket connects / DNS lookups attempted (all blocked): {len(BLOCKED)} {BLOCKED[:3]}")


if __name__ == "__main__":
    main()
