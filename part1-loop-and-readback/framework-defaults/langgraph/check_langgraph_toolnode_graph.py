"""
A hand-built LangGraph graph with langgraph.prebuilt.ToolNode, every default left alone.

The companion to check_langgraph_defaults.py, which covers create_agent and create_react_agent.
This one builds the graph from the LangGraph docs pattern by hand:

    StateGraph(MessagesState): START -> "model" -> tools_condition -> "tools" -> "model"

with ToolNode(tools) and no handle_tool_errors argument, and asks two questions:

  1. When the ticket tool raises the 422, does the run stop (as with create_agent), or does
     the model read something?
  2. What is the default loop limit, and how many model calls does it allow? A run with a
     non-default recursion_limit=50 shows how the step count maps to model calls.

The model is a scripted fake on langchain_core's BaseChatModel. No network: provider keys are
removed, tracing is off, and every socket connect is blocked. Run from this folder with:

    python -I check_langgraph_toolnode_graph.py > output-toolnode-graph.txt

The default-limit run plays thousands of fake turns.
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

import inspect
import json
from importlib.metadata import version
from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
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
    """Fake chat model: answers from a script and counts its calls."""

    _responder: Callable[[int], AIMessage] = PrivateAttr()
    _count: int = PrivateAttr(default=0)

    def __init__(self, responder: Callable[[int], AIMessage], **kw: Any):
        super().__init__(**kw)
        self._responder = responder

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        turn = self._count
        self._count += 1
        return ChatResult(generations=[ChatGeneration(message=self._responder(turn))])


def call(name: str, args: dict, cid: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid}])


def build_graph(model: ScriptedChatModel, tools: list):
    """The hand-built pattern from the LangGraph docs. ToolNode gets no keyword arguments."""
    from langgraph.graph import START, MessagesState, StateGraph
    from langgraph.prebuilt import ToolNode, tools_condition

    bound = model.bind_tools(tools)

    def call_model(state: MessagesState) -> dict:
        return {"messages": [bound.invoke(state["messages"])]}

    g = StateGraph(MessagesState)
    g.add_node("model", call_model)
    g.add_node("tools", ToolNode(tools))
    g.add_edge(START, "model")
    g.add_conditional_edges("model", tools_condition)
    g.add_edge("tools", "model")
    return g.compile()


USER = HumanMessage("File a high-priority ticket: CSV export times out")


def outcome(fn: Callable[[], Any]) -> None:
    try:
        out = fn()
        print("    run outcome: RETURNED to caller (no exception)")
        print(f"    final message: {type(out['messages'][-1]).__name__} {out['messages'][-1].content!r}")
    except Exception as e:  # noqa: BLE001
        print("    run outcome: EXCEPTION propagated to caller")
        print(f"    exception type: {type(e).__module__}.{type(e).__qualname__}")
        print(f"    exception str : {str(e).splitlines()[0]}")


def main() -> None:
    for p in ("langchain-core", "langgraph", "langgraph-prebuilt"):
        print(f"{p}=={version(p)}")
    from langgraph._internal._config import DEFAULT_RECURSION_LIMIT
    from langgraph.prebuilt import ToolNode
    print(f"langgraph DEFAULT_RECURSION_LIMIT = {int(DEFAULT_RECURSION_LIMIT)}")
    default_handler = inspect.signature(ToolNode.__init__).parameters["handle_tool_errors"].default
    print(f"ToolNode(...) handle_tool_errors default: {getattr(default_handler, '__name__', default_handler)!r}")

    print("\n##### DEFAULTS UNTOUCHED: hand-built StateGraph + ToolNode(tools) #####")

    print("\n=== F1 tool raises ServerValidationError (priority='high')")
    TOOL_RUNS["create_ticket"] = 0
    high = call("create_ticket", {"title": "CSV export times out", "priority": "high"}, "call_1")
    model = ScriptedChatModel(lambda t: high if t == 0 else AIMessage(content="Ticket handled."))
    graph = build_graph(model, [create_ticket])
    print(f"    recursion_limit carried on the compiled graph: {(graph.config or {}).get('recursion_limit')!r}")
    outcome(lambda: graph.invoke({"messages": [USER]}))
    print(f"    tool function executions: {TOOL_RUNS['create_ticket']}")
    print(f"    model calls made: {model._count}")
    print("    turn 2: " + ("NEVER HAPPENED (the model was not called again)" if model._count < 2
                            else "the model was called again"))

    for lim in (50, None):
        label = "DEFAULT limit" if lim is None else f"NON-DEFAULT recursion_limit={lim}"
        print(f"\n=== F3 loop limit: model calls ping() forever, {label}", flush=True)
        TOOL_RUNS["ping"] = 0
        model = ScriptedChatModel(lambda t: call("ping", {}, f"call_{t}"))
        graph = build_graph(model, [ping])
        cfg = None if lim is None else {"recursion_limit": lim}
        outcome(lambda: graph.invoke({"messages": [USER]}, cfg))
        print(f"    model calls made: {model._count}   ping executions: {TOOL_RUNS['ping']}")

    print(f"\nsocket connects attempted (all blocked): {len(BLOCKED)} {BLOCKED[:3]}")


if __name__ == "__main__":
    main()
