"""Pattern 4: at the turn limit the user still gets an answer."""

from __future__ import annotations

import asyncio
import itertools

import pytest
from agents import Agent, MaxTurnsExceeded, RunConfig, Runner
from conftest import PROMPT, TITLE

from p1_error_notes import ticket_error_note
from p4_turn_limit import ERROR_HANDLERS
from run_state import RunState
from scripted_model import ScriptedModel, ToolCall
from ticket_service import TicketService
from tools import make_create_ticket

WRONG = ["high", "urgent", "High", "HIGH", "1", "p1"]


def never_right() -> ScriptedModel:
    """A model that changes its value every time but never sends a valid code."""
    return ScriptedModel([ToolCall("create_ticket", {"title": TITLE, "priority": v})
                          for v in itertools.islice(itertools.cycle(WRONG), 20)])


def agent_for(model):
    return Agent(name="ops", model=model, tools=[
        make_create_ticket(TicketService(), failure_error_function=ticket_error_note)])


def test_a_limit_of_two_turns_ends_with_an_answer_not_an_exception():
    state = RunState()
    result = asyncio.run(Runner.run(
        agent_for(never_right()), PROMPT, context=state, max_turns=2,
        error_handlers=ERROR_HANDLERS, run_config=RunConfig(tracing_disabled=True),
    ))
    assert result.final_output == (
        "I could not finish your request in 2 steps. Done: Nothing was saved. "
        "What failed: 2 tool calls were rejected (create_ticket). "
        "Next: a person on the team has your request and will finish it."
    )
    assert state.handoffs == [result.final_output]


def test_without_a_handler_the_limit_only_raises():
    with pytest.raises(MaxTurnsExceeded):
        asyncio.run(Runner.run(agent_for(never_right()), PROMPT, context=RunState(),
                               max_turns=2, run_config=RunConfig(tracing_disabled=True)))
