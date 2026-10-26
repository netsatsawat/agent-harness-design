"""Pattern 1: the model reads the approved note, per tool or run-wide."""

from __future__ import annotations

import asyncio

from agents import Agent, RunConfig, Runner
from conftest import PROMPT, TITLE

from p1_error_notes import APPROVED_NOTES, approved_note, run_wide_formatter, ticket_error_note
from run_state import RunState
from scripted_model import Reply, ScriptedModel, ToolCall
from ticket_service import TicketService, ValidationError
from tools import make_create_ticket

SDK_FIXED_LINE = "An error occurred while running the tool. Please try again."


def fix_after_one_error() -> ScriptedModel:
    return ScriptedModel([
        ToolCall("create_ticket", {"title": TITLE, "priority": "high"}),
        ToolCall("create_ticket", {"title": TITLE, "priority": "P1"}),
        Reply("Done."),
    ])


def run(agent, run_config=None, state=None):
    return asyncio.run(Runner.run(
        agent, PROMPT, context=state, run_config=run_config or RunConfig(tracing_disabled=True),
    ))


def test_note_names_field_values_with_meaning_and_next_step():
    error = ValidationError("priority", "high", "Input should be 'P0', 'P1' or 'P2'")
    note = approved_note(error)
    assert note == APPROVED_NOTES["priority"]
    for part in ("priority", "P0 (critical)", "P1 (high)", "P2 (normal)", "Next step"):
        assert part in note
    assert approved_note(RuntimeError("connection reset by peer")) is None


def test_per_tool_handler_sends_the_note():
    model, service, state = fix_after_one_error(), TicketService(), RunState()
    tool = make_create_ticket(service, failure_error_function=ticket_error_note)
    agent = Agent(name="ops", tools=[tool], model=model)
    run(agent, state=state)
    assert model.tool_outputs_read == [
        APPROVED_NOTES["priority"], "Created TCK-1042 with priority P1 (high).",
    ]
    assert [f.field for f in state.failures] == ["priority"]


def test_run_wide_formatter_sends_the_note_for_tools_on_the_default_handler():
    model, service = fix_after_one_error(), TicketService()
    tool = make_create_ticket(service)   # no failure_error_function of its own
    agent = Agent(name="ops", tools=[tool], model=model)
    run(agent, RunConfig(tracing_disabled=True, tool_error_formatter=run_wide_formatter))
    assert model.tool_outputs_read[0] == APPROVED_NOTES["priority"]


def test_without_either_the_model_reads_the_sdk_fixed_line():
    model, service = fix_after_one_error(), TicketService()
    agent = Agent(name="ops", tools=[make_create_ticket(service)], model=model)
    run(agent)
    assert model.tool_outputs_read[0] == SDK_FIXED_LINE   # the allowed codes never reach the model
