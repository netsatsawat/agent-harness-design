"""
What the model reads after a failed tool call in LangChain 1.x / LangGraph, with defaults.

Runs the REAL agent loops with every default left alone:
  - langchain.agents.create_agent             (LangChain 1.x, the current entry point)
  - langgraph.prebuilt.create_react_agent     (deprecated since LangGraph v1, still shipped)
Both build a langgraph.prebuilt.ToolNode with its default handle_tool_errors.

The model is a scripted fake built on langchain_core's BaseChatModel extension point. It
records every message list it is handed, so "what the model reads on turn 2" is captured
from the loop itself, not reconstructed.

No network: provider keys are removed, tracing is off, and every socket connect is
blocked (the script reports how many were attempted). Run from this folder with:

    python -I check_langgraph_defaults.py > output.txt
    python -I check_langgraph_defaults.py --full-default-loop > output-full-default-loop.txt

The second run plays thousands of fake turns, because the default limits are 9_999 / 10_007 steps.
"""

from __future__ import annotations

import os

for k in list(os.environ):
    if k.endswith("_API_KEY") or k.startswith(("LANGCHAIN_", "LANGSMITH_", "LANGGRAPH_")):
        os.environ.pop(k)
os.environ.update({
    "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false",
    "OTEL_SDK_DISABLED": "true", "DO_NOT_TRACK": "1",
})

import socket

BLOCKED: list[str] = []


def _blocked(*a, **k):
    BLOCKED.append(repr(a[:2]))
    raise OSError("network blocked by check script")


socket.socket.connect = _blocked  # type: ignore[assignment]
socket.socket.connect_ex = _blocked  # type: ignore[assignment]
socket.create_connection = _blocked  # type: ignore[assignment]
socket.getaddrinfo = _blocked  # type: ignore[assignment]

import json
import sys
import warnings
from importlib.metadata import version
from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from pydantic import PrivateAttr


# ---- copied verbatim from part1-loop-and-readback/experiment/servers.py -------------------
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
# -------------------------------------------------------------------------------------------

TOOL_RUNS = {"create_ticket": 0, "ping": 0}


@tool
def create_ticket(title: str, priority: str) -> dict:
    """Create a support ticket. priority is the ticket priority."""
    TOOL_RUNS["create_ticket"] += 1
    return ticket_server(title, priority)


@tool
def ping() -> str:
    """Harmless tool for the loop-limit test."""
    TOOL_RUNS["ping"] += 1
    return "pong"


class ScriptedChatModel(BaseChatModel):
    """Fake chat model: answers from a script and records what each turn was given."""

    _responder: Callable[[int], AIMessage] = PrivateAttr()
    _seen: list[list[BaseMessage]] = PrivateAttr(default_factory=list)
    _count: int = PrivateAttr(default=0)
    _keep: bool = PrivateAttr(default=True)

    def __init__(self, responder: Callable[[int], AIMessage], keep: bool = True, **kw: Any):
        super().__init__(**kw)
        self._responder, self._keep = responder, keep

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        turn = self._count
        self._count += 1
        if self._keep:
            self._seen.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=self._responder(turn))])


def call(name: str, args: dict, cid: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid}])


def script(*msgs: AIMessage) -> Callable[[int], AIMessage]:
    def r(turn: int) -> AIMessage:
        return msgs[turn] if turn < len(msgs) else AIMessage(content="(script ended)")
    return r


def dump_tool_message(m: BaseMessage) -> dict:
    d = {"class": type(m).__name__, "type(role)": m.type, "content": m.content}
    if isinstance(m, ToolMessage):
        d.update(status=m.status, name=m.name, tool_call_id=m.tool_call_id)
    if m.additional_kwargs:
        d["additional_kwargs"] = m.additional_kwargs
    return d


def build(kind: str, model: ScriptedChatModel, tools: list, **non_default: Any):
    if kind == "create_agent":
        from langchain.agents import create_agent
        return create_agent(model, tools, **non_default)
    from langgraph.prebuilt import create_react_agent
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        g = create_react_agent(model, tools, **non_default)
    for x in w:
        print(f"    [warning at build] {x.category.__name__}: {x.message}")
    return g


USER = HumanMessage("File a high-priority ticket: CSV export times out")


def run_once(label: str, kind: str, first_call: AIMessage, **non_default: Any) -> None:
    print(f"\n=== {label}  [{kind}]")
    TOOL_RUNS["create_ticket"] = 0
    model = ScriptedChatModel(script(first_call, AIMessage(content="Ticket handled.")))
    agent = build(kind, model, [create_ticket], **non_default)
    print(f"    turn 1 tool call: {first_call.tool_calls[0]['name']}"
          f"({json.dumps(first_call.tool_calls[0]['args'])})")
    try:
        out = agent.invoke({"messages": [USER]})
        print("    run outcome: RETURNED to caller (no exception)")
        print(f"    final message: {out['messages'][-1].content!r}")
    except Exception as e:  # noqa: BLE001
        print("    run outcome: EXCEPTION propagated to caller")
        print(f"    exception type: {type(e).__module__}.{type(e).__qualname__}")
        print(f"    exception str : {str(e)}")
    print(f"    tool function executions: {TOOL_RUNS['create_ticket']}")
    print(f"    model calls made: {model._count}")
    if model._count >= 2:
        turn2 = model._seen[1]
        tm = [m for m in turn2 if isinstance(m, ToolMessage)]
        print("    turn 2: model received this tool-result message:")
        for m in tm:
            print("      " + json.dumps(dump_tool_message(m), ensure_ascii=False))
            print("      content, printed raw:")
            for line in str(m.content).split("\n"):
                print("        | " + line)
    else:
        print("    turn 2: NEVER HAPPENED (the model was not called again)")


def run_loop(kind: str, recursion_limit: int | None = None) -> None:
    lim = "DEFAULT limit" if recursion_limit is None else f"NON-DEFAULT recursion_limit={recursion_limit}"
    print(f"\n=== F3 turn limit: model calls ping() forever, {lim}  [{kind}]", flush=True)
    TOOL_RUNS["ping"] = 0

    def responder(t: int) -> AIMessage:
        if t and t % 500 == 0:
            print(f"    ... {t} model calls so far", file=sys.stderr, flush=True)
        return call("ping", {}, f"call_{t}")

    model = ScriptedChatModel(responder, keep=False)
    agent = build(kind, model, [ping])
    rl = getattr(agent, "config", None) or {}
    print(f"    recursion_limit carried on the compiled graph: {rl.get('recursion_limit')!r}")
    try:
        cfg = None if recursion_limit is None else {"recursion_limit": recursion_limit}
        out = agent.invoke({"messages": [USER]}, cfg)
        last = out["messages"][-1]
        print("    run outcome: RETURNED to caller (no exception)")
        print(f"    final message: {type(last).__name__} {last.content!r}")
        print(f"    final message has tool_calls: {bool(getattr(last, 'tool_calls', None))}")
    except Exception as e:  # noqa: BLE001
        print("    run outcome: EXCEPTION propagated to caller")
        print(f"    exception type: {type(e).__module__}.{type(e).__qualname__}")
        print(f"    exception str : {str(e)}")
    print(f"    model calls made: {model._count}   ping executions: {TOOL_RUNS['ping']}")


def main() -> None:
    for p in ("langchain", "langchain-core", "langgraph", "langgraph-prebuilt"):
        print(f"{p}=={version(p)}")
    from langgraph._internal._config import DEFAULT_RECURSION_LIMIT
    from langchain_core.runnables.config import DEFAULT_RECURSION_LIMIT as CORE_DEFAULT
    print(f"langgraph DEFAULT_RECURSION_LIMIT = {int(DEFAULT_RECURSION_LIMIT)}"
          f"  (langchain_core's own constant, not used by langgraph: {CORE_DEFAULT})")

    print("\n##### DEFAULTS UNTOUCHED #####")
    high = call("create_ticket", {"title": "CSV export times out", "priority": "high"}, "call_1")
    for kind in ("create_agent", "create_react_agent"):
        run_once("F1 tool raises ServerValidationError (priority='high')", kind, high)

    bad_type = call("create_ticket", {"title": "CSV export times out", "priority": 123}, "call_1")
    missing = call("create_ticket", {"title": "CSV export times out"}, "call_1")
    for kind in ("create_agent", "create_react_agent"):
        run_once("F1b bad args: priority=123 (fails the tool's own schema)", kind, bad_type)
        run_once("F1b bad args: priority missing", kind, missing)

    if "--full-default-loop" in sys.argv:
        # Slow: thousands of fake turns, because the default limits are 9_999 / 10_007 steps.
        for kind in ("create_agent", "create_react_agent"):
            run_loop(kind)
        print(f"\nsocket connects attempted (all blocked): {len(BLOCKED)} {BLOCKED[:3]}")
        return
    for kind in ("create_agent", "create_react_agent"):
        print(f"\n    (default loop limit is run by: python -I {os.path.basename(sys.argv[0])}"
              " --full-default-loop)")
        agent = build(kind, ScriptedChatModel(script()), [ping])
        rl = (getattr(agent, "config", None) or {}).get("recursion_limit")
        print(f"    [{kind}] recursion_limit carried on the compiled graph: {rl!r}"
              f" -> falls back to langgraph DEFAULT_RECURSION_LIMIT when None")

    print("\n##### NON-DEFAULT limit, F3 only: same loop, small limits so it ends fast #####")
    print("    (an odd and an even limit: create_react_agent's 'need more steps' stop depends on it;")
    print("     the shipped defaults are 9_999 for create_agent and 10_007 for create_react_agent)")
    for lim in (11, 12):
        for kind in ("create_agent", "create_react_agent"):
            run_loop(kind, recursion_limit=lim)

    print("\n##### NON-DEFAULT, for F2 only: the knobs that replace the text #####")
    from langchain.agents.middleware import ToolErrorMiddleware
    from langgraph.prebuilt import ToolNode

    def team_note(exc: Exception, request: Any) -> str:
        return ("create_ticket failed: priority must be one of P0 (critical), "
                "P1 (high), P2 (normal). Map the user's word to a code and call again.")

    run_once("F2 knob: create_agent(middleware=[ToolErrorMiddleware(on_error=...)])",
             "create_agent", high, middleware=[ToolErrorMiddleware(on_error=team_note)])

    def team_note_toolnode(e: ServerValidationError) -> str:
        return team_note(e, None)

    print("\n    (create_react_agent accepts a pre-built ToolNode in place of the tools list)")
    for flag_label, flag in (("handle_tool_errors=team_note_toolnode", team_note_toolnode),
                             ("handle_tool_errors=True", True)):
        print(f"\n=== F2 knob: create_react_agent(ToolNode([create_ticket], {flag_label}))")
        TOOL_RUNS["create_ticket"] = 0
        model = ScriptedChatModel(script(high, AIMessage(content="Ticket handled.")))
        from langgraph.prebuilt import create_react_agent
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            agent = create_react_agent(
                model, ToolNode([create_ticket], handle_tool_errors=flag))
        agent.invoke({"messages": [USER]})
        tm = [m for m in model._seen[1] if isinstance(m, ToolMessage)][0]
        print("    turn 2: model received " + json.dumps(dump_tool_message(tm), ensure_ascii=False))
        print("      content, printed raw:")
        for line in str(tm.content).split("\n"):
            print("        | " + line)

    print(f"\nsocket connects attempted (all blocked): {len(BLOCKED)} {BLOCKED[:3]}")


if __name__ == "__main__":
    main()
