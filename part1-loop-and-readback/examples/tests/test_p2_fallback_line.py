"""Pattern 2: approved text to the model, the full exception to your logs."""

from __future__ import annotations

import asyncio
import logging
import traceback

from agents import Agent, RunConfig, Runner, function_tool
from conftest import PROMPT

from p1_error_notes import APPROVED_NOTES
from p2_fallback_line import FIXED_LINE, note_or_fixed_line, unsafe_findings
from run_state import RunState
from scripted_model import Reply, ScriptedModel, ToolCall
from ticket_service import ValidationError

LEAKY = RuntimeError(
    "could not connect to postgres://admin:hunter2@db.internal:5432/tickets "
    "(token sk-live-1234567890abcdef)")


def crash() -> str:
    """Look up the on-call engineer."""
    raise LEAKY


def test_unknown_error_gets_the_fixed_line_and_a_log_entry(caplog):
    model, state = ScriptedModel([ToolCall("crash", {}), Reply("Sorry.")]), RunState()
    agent = Agent(name="ops", model=model,
                  tools=[function_tool(crash, failure_error_function=note_or_fixed_line)])
    with caplog.at_level(logging.WARNING, logger="harness.missing_note"):
        asyncio.run(Runner.run(agent, PROMPT, context=state,
                               run_config=RunConfig(tracing_disabled=True)))
    assert model.tool_outputs_read == [FIXED_LINE]
    assert unsafe_findings(model.tool_outputs_read[0]) == []
    [record] = caplog.records
    assert "no approved note for RuntimeError from tool crash" in record.getMessage()
    assert record.exc_info[1] is LEAKY   # the full exception is in the log, not in the model's input
    assert state.failures[0].model_read == FIXED_LINE


def test_known_error_gets_its_note_and_no_log_entry(caplog):
    error = ValidationError("priority", "high", "Input should be 'P0', 'P1' or 'P2'")
    with caplog.at_level(logging.WARNING, logger="harness.missing_note"):
        assert note_or_fixed_line(None, error) == APPROVED_NOTES["priority"]
    assert caplog.records == []


def test_check_flags_raw_exception_text():
    raw_422 = str(ValidationError("priority", "high", "Input should be 'P0', 'P1' or 'P2'"))
    assert unsafe_findings(raw_422) == ["raw HTTP body"]
    assert unsafe_findings(str(LEAKY)) == ["credential in URL", "token"]
    try:
        raise LEAKY
    except RuntimeError:
        tb = traceback.format_exc()
    assert {"stack trace", "file path"} <= set(unsafe_findings(tb))
    assert unsafe_findings("GET http://localhost:8080/admin failed") == ["internal URL"]


def test_check_passes_every_approved_text():
    for text in [FIXED_LINE, *APPROVED_NOTES.values()]:
        assert unsafe_findings(text) == [], text
