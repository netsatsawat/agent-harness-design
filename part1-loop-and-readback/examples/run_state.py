"""
The record the harness keeps for one run, passed to the SDK as the run context:

    state = RunState()
    await Runner.run(agent, request, context=state)

Tools, error handlers and guardrails all receive it as ctx.context. The patterns use it to know
what was written, which calls failed and what the model read after each failure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agents.tool_context import ToolContext


def call_key(tool_name: str, arguments: str) -> tuple[str, str]:
    """A tool call as its name plus its arguments, with key order and spacing made uniform, so
    two calls that send the same values compare equal."""
    try:
        canonical = json.dumps(json.loads(arguments or "{}"), sort_keys=True)
    except json.JSONDecodeError:
        canonical = arguments
    return tool_name, canonical


@dataclass
class Failure:
    tool: str
    arguments: str
    model_read: str           # the exact text the harness sent back to the model
    field: str | None = None  # the field the service rejected, when the error names one


@dataclass
class RunState:
    writes: list[str] = field(default_factory=list)       # read-back line of each saved write
    failures: list[Failure] = field(default_factory=list)  # every failed call, in order
    handoffs: list[str] = field(default_factory=list)      # what was passed to a person

    def failed_before(self, tool: str, arguments: str) -> Failure | None:
        key = call_key(tool, arguments)
        for f in reversed(self.failures):
            if call_key(f.tool, f.arguments) == key:
                return f
        return None


def record_failure(ctx: Any, model_read: str, field: str | None = None) -> str:
    """Note a failed call in the run's RunState (if the run has one) and return the text."""
    state = getattr(ctx, "context", None)
    if isinstance(ctx, ToolContext) and isinstance(state, RunState):
        state.failures.append(Failure(ctx.tool_name, ctx.tool_arguments, model_read, field))
    return model_read
