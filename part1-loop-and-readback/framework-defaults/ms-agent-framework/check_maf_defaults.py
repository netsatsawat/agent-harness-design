"""
What Microsoft Agent Framework (agent-framework-core 1.23.0) hands the model after a tool fails,
with every harness default left untouched. No network, no API key, no model call.

The model is a scripted fake built on the framework's own extension point: a BaseChatClient
subclass that implements _inner_get_response, wrapped in the same three layers the shipped
provider clients use (FunctionInvocationLayer, ChatMiddlewareLayer, ChatTelemetryLayer, in that
order, as OpenAIChatCompletionClient does at python-1.23.0). The REAL Agent.run() and the REAL
function-invocation loop do everything else.

Run from this folder with:

    python -I check_maf_defaults.py > output.txt

The script removes the provider keys and turns telemetry off before it imports the framework.

Scenarios 1-6 use defaults only. Scenarios 7-9 each change ONE knob, to show what it does.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import logging
import os
import sys
from typing import Any

for key in ("OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AZURE_AI_PROJECT_ENDPOINT"):
    os.environ.pop(key, None)
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("DO_NOT_TRACK", "1")

from agent_framework import (  # noqa: E402
    Agent,
    BaseChatClient,
    ChatMiddlewareLayer,
    ChatResponse,
    Content,
    FunctionInvocationContext,
    FunctionInvocationLayer,
    Message,
    function_middleware,
    tool,
)
from agent_framework.observability import ChatTelemetryLayer  # noqa: E402


# --- copied verbatim from part1-loop-and-readback/experiment/servers.py ----------------------
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
# ---------------------------------------------------------------------------------------------


CALLED_BODY: list[dict] = []


def make_create_ticket(**tool_kwargs: Any):
    @tool(**tool_kwargs)
    def create_ticket(title: str, priority: str) -> str:
        """Create a support ticket.

        Args:
            title: Short title for the ticket.
            priority: Priority for the ticket.
        """
        CALLED_BODY.append({"title": title, "priority": priority})
        return json.dumps(ticket_server(title, priority))

    return create_ticket


@tool
def ping() -> str:
    """Always succeeds."""
    CALLED_BODY.append({})
    return "pong"


# --- scripted fake model ----------------------------------------------------------------------
class ScriptedRawClient(BaseChatClient):
    """A model that follows a script. It records every request the loop sends it."""

    OTEL_PROVIDER_NAME = "fake"

    def __init__(self, *, policy, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.policy = policy
        self.requests: list[dict] = []

    def _inner_get_response(self, *, messages, stream, options, **kwargs):
        if stream:
            raise NotImplementedError("non-streaming only")

        async def _respond() -> ChatResponse:
            turn = len(self.requests)
            self.requests.append({
                "turn": turn + 1,
                "tool_choice": options.get("tool_choice"),
                "tools_offered": [getattr(t, "name", str(t)) for t in (options.get("tools") or [])],
                "messages": list(messages),
            })
            contents = self.policy(turn, options)
            return ChatResponse(messages=[Message(role="assistant", contents=contents)],
                                response_id=f"fake-{turn + 1}")

        return _respond()


class FakeChatClient(FunctionInvocationLayer, ChatMiddlewareLayer, ChatTelemetryLayer,
                     ScriptedRawClient):
    """Same layer order as OpenAIChatCompletionClient at python-1.23.0."""


def call(turn: int, args: Any, name: str = "create_ticket") -> Content:
    return Content.from_function_call(
        call_id=f"call_{turn + 1}", name=name,
        arguments=args if isinstance(args, str) else json.dumps(args),
    )


GOOD = {"title": "CSV export times out", "priority": "high"}


def once_then_text(args: Any):
    def policy(turn, options):
        if turn == 0:
            return [call(turn, args)]
        return [Content.from_text("Done.")]
    return policy


def forever(args: Any, name: str = "create_ticket", ignore_tool_choice: bool = False):
    def policy(turn, options):
        if options.get("tool_choice") == "none" and not ignore_tool_choice:
            return [Content.from_text("I could not finish.")]
        return [call(turn, args, name)]
    return policy


# --- capture helpers --------------------------------------------------------------------------
def dump_content(c: Content) -> dict:
    d: dict[str, Any] = {"type": c.type}
    for f in ("call_id", "name", "arguments", "text", "result", "exception", "status"):
        v = getattr(c, f, None)
        if v is not None:
            d[f] = v
    if getattr(c, "items", None):
        d["items"] = [{"type": i.type, "text": i.text} for i in c.items]
    if c.type == "function_result":
        d["to_dict()['exception']"] = c.to_dict().get("exception")
    if c.type == "function_approval_request" and c.function_call is not None:
        d["function_call"] = dump_content(c.function_call)
    return d


def dump_message(m: Message) -> dict:
    return {"role": m.role, "contents": [dump_content(c) for c in m.contents]}


def tool_messages(req: dict) -> list[dict]:
    return [dump_message(m) for m in req["messages"] if m.role == "tool"]


async def run_agent(policy, tools, client_kwargs=None, agent_kwargs=None, user="Open a high "
                    "priority ticket: CSV export on the reports page times out."):
    CALLED_BODY.clear()
    client = FakeChatClient(policy=policy, **(client_kwargs or {}))
    agent = Agent(client=client, tools=tools, **(agent_kwargs or {}))
    out: dict[str, Any] = {}
    try:
        resp = await agent.run(user)
        out["run_outcome"] = "returned (no exception)"
        out["final_text"] = resp.text
        out["user_input_requests"] = [dump_content(c) for c in resp.user_input_requests]
    except Exception as exc:  # noqa: BLE001
        out["run_outcome"] = f"raised {type(exc).__module__}.{type(exc).__name__}: {exc}"
    out["model_calls"] = len(client.requests)
    out["tool_body_ran"] = len(CALLED_BODY)
    out["tool_choice_per_turn"] = [r["tool_choice"] for r in client.requests]
    return out, client


def section(title: str) -> None:
    print("\n" + "=" * 100 + f"\n{title}\n" + "=" * 100)


async def main() -> None:
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout,
                        format="[log %(levelname)s %(name)s] %(message)s")
    print("python", sys.version.split()[0])
    print("agent-framework-core", importlib.metadata.version("agent-framework-core"))
    from agent_framework._tools import normalize_function_invocation_configuration
    print("default FunctionInvocationConfiguration:",
          {k: v for k, v in normalize_function_invocation_configuration(None).items()
           if k != "additional_tools"})
    print("default approval_mode on @tool:", make_create_ticket().approval_mode)
    print("default max_invocations / max_invocation_exceptions on @tool:",
          make_create_ticket().max_invocations, make_create_ticket().max_invocation_exceptions)

    section("1. DEFAULTS: tool raises ServerValidationError on priority='high'. "
            "What does the model get on turn 2?")
    out, client = await run_agent(once_then_text(GOOD), [make_create_ticket()])
    print(json.dumps(out, indent=2, default=str))
    print("turn-2 request, tool-role messages exactly as the fake model received them:")
    print(json.dumps(tool_messages(client.requests[1]), indent=2, default=str))
    print("turn-2 request, all message roles in order:",
          [m.role for m in client.requests[1]["messages"]])

    section("2. DEFAULTS: arguments fail the tool's own schema (priority=123, int for a str)")
    out, client = await run_agent(once_then_text({"title": "CSV export times out", "priority": 123}),
                                  [make_create_ticket()])
    print(json.dumps(out, indent=2, default=str))
    print(json.dumps(tool_messages(client.requests[1]), indent=2, default=str))

    section("3. DEFAULTS: required argument missing ({'title': ...} only)")
    out, client = await run_agent(once_then_text({"title": "CSV export times out"}),
                                  [make_create_ticket()])
    print(json.dumps(out, indent=2, default=str))
    print(json.dumps(tool_messages(client.requests[1]), indent=2, default=str))

    section("4. DEFAULTS: arguments are not valid JSON")
    out, client = await run_agent(once_then_text('{"title": "CSV export times out", "priority": "hi'),
                                  [make_create_ticket()])
    print(json.dumps(out, indent=2, default=str))
    print(json.dumps(tool_messages(client.requests[1]), indent=2, default=str))

    section("5. DEFAULTS: model retries the failing call forever "
            "(max_consecutive_errors_per_request=3)")
    out, client = await run_agent(forever(GOOD), [make_create_ticket()])
    print(json.dumps(out, indent=2, default=str))
    last = client.requests[-1]
    print("last request: tool_choice =", last["tool_choice"],
          "| tool results the model has seen:",
          sum(1 for m in last["messages"] if m.role == "tool"))
    print("5b. same, but the fake ignores tool_choice='none' and calls the tool again anyway:")
    out, client = await run_agent(forever(GOOD, ignore_tool_choice=True), [make_create_ticket()])
    print(json.dumps(out, indent=2, default=str))

    section("6. DEFAULTS: tool always succeeds, model calls it forever (max_iterations=40)")
    out, client = await run_agent(forever({}, name="ping"), [ping])
    print(json.dumps({k: v for k, v in out.items() if k != "tool_choice_per_turn"}, indent=2))
    print("tool_choice on turns 1, 40, 41:", out["tool_choice_per_turn"][0],
          out["tool_choice_per_turn"][39], out["tool_choice_per_turn"][40])
    print("6b. same, but the fake ignores tool_choice='none' on the final call:")
    out, client = await run_agent(forever({}, name="ping", ignore_tool_choice=True), [ping])
    print(json.dumps({k: v for k, v in out.items() if k != "tool_choice_per_turn"}, indent=2))

    section("7. ONE KNOB: include_detailed_errors=True (global, on the client)")
    out, client = await run_agent(
        once_then_text(GOOD), [make_create_ticket()],
        client_kwargs={"function_invocation_configuration": {"include_detailed_errors": True}})
    print(json.dumps(out, indent=2, default=str))
    print(json.dumps(tool_messages(client.requests[1]), indent=2, default=str))

    section("8. ONE KNOB: function middleware that replaces the failure text with the team's note")

    @function_middleware
    async def error_note(context: FunctionInvocationContext, call_next) -> None:
        try:
            await call_next()
        except ServerValidationError as exc:
            if exc.field_name == "priority":
                context.result = ("priority is not valid. Allowed values: P0 (critical), "
                                  "P1 (high), P2 (normal). Next step: call create_ticket again "
                                  "with priority set to one of these codes.")
            else:
                raise

    out, client = await run_agent(once_then_text(GOOD), [make_create_ticket()],
                                  agent_kwargs={"middleware": [error_note]})
    print(json.dumps(out, indent=2, default=str))
    print(json.dumps(tool_messages(client.requests[1]), indent=2, default=str))
    print("8b. same middleware, model retries forever: does the 3-error cap still fire?")
    out, client = await run_agent(forever(GOOD), [make_create_ticket()],
                                  agent_kwargs={"middleware": [error_note]})
    print(json.dumps({k: v for k, v in out.items() if k != "tool_choice_per_turn"}, indent=2))
    print("tool_choice on the last request:", out["tool_choice_per_turn"][-1])

    section("9. ONE KNOB: @tool(approval_mode='always_require')")
    out, client = await run_agent(once_then_text(GOOD),
                                  [make_create_ticket(approval_mode="always_require")])
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
