"""
Pattern 1: write the fix into the error.

After a failed call, the model knows only the text the harness sends back. For each failure a
tool can predict, send a short note your team approved: the field, the allowed values with their
meaning, and the next step.

Two places to hook it in the OpenAI Agents SDK (0.24.0):

  - per tool:  function_tool(fn, failure_error_function=ticket_error_note)
  - run-wide:  RunConfig(tool_error_formatter=run_wide_formatter)
               It formats exceptions only for tools that have no failure_error_function of their
               own. A tool with its own handler keeps it.

Both return the SDK's own fixed line for an error with no approved note (p2_fallback_line.py adds
a log entry to that case).
"""

from __future__ import annotations

from typing import Any

from agents import RunContextWrapper, ToolErrorFormatterArgs
from agents.tool import default_tool_error_function

from run_state import record_failure
from ticket_service import ValidationError

# Field, allowed values with their meaning, next step. Nothing else: no raw error, no stack trace.
APPROVED_NOTES = {
    "priority": (
        "priority is not valid. Allowed values: P0 (critical), P1 (high), P2 (normal). "
        "Next step: call create_ticket again with priority set to one of these codes."
    ),
    "title": (
        "title is empty. Next step: call create_ticket again with a short summary of the issue "
        "in title."
    ),
}


def approved_note(error: BaseException | None) -> str | None:
    """The approved note for an error, or None when the team has not written one yet."""
    if isinstance(error, ValidationError):
        return APPROVED_NOTES.get(error.field)
    return None


def error_field(error: BaseException | None) -> str | None:
    return error.field if isinstance(error, ValidationError) else None


def ticket_error_note(ctx: RunContextWrapper[Any], error: Exception) -> str:
    """A failure_error_function for create_ticket."""
    note = approved_note(error)
    text = note if note is not None else default_tool_error_function(ctx, error)
    return record_failure(ctx, text, field=error_field(error))


def run_wide_formatter(args: ToolErrorFormatterArgs[Any]) -> str | None:
    """A RunConfig.tool_error_formatter: the approved note for any tool on the SDK default
    handler. Approval rejections and unknown tools keep the SDK's own message (None)."""
    if args.kind != "tool_exception":
        return None
    note = approved_note(args.error)
    text = note if note is not None else args.default_message
    return record_failure(args.run_context, text, field=error_field(args.error))
