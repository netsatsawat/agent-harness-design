"""Pattern 3: grade the stored value, not the accepted call."""

from __future__ import annotations

import asyncio

from agents import Agent, RunConfig, Runner
from conftest import PROMPT, TITLE

from p1_error_notes import ticket_error_note
from p3_read_back import check_stored, read_back
from run_state import RunState
from scripted_model import Reply, ScriptedModel, ToolCall
from ticket_service import TicketService
from tools import make_create_ticket


def run_with_priority(priority: str) -> tuple[TicketService, ScriptedModel, RunState, str]:
    service, state = TicketService(), RunState()
    model = ScriptedModel([
        ToolCall("create_ticket", {"title": TITLE, "priority": priority}),
        Reply("Your ticket is open."),
    ])
    agent = Agent(name="ops", model=model,
                  tools=[make_create_ticket(service, failure_error_function=ticket_error_note)])
    result = asyncio.run(Runner.run(agent, PROMPT, context=state,
                                    run_config=RunConfig(tracing_disabled=True)))
    return service, model, state, str(result.final_output)


def test_read_back_names_the_stored_value_and_its_meaning():
    service = TicketService()
    ticket_id = service.create(TITLE, "P0")
    assert read_back(service, ticket_id) == "Created TCK-1042 with priority P0 (critical)."


def test_an_accepted_wrong_value_looks_like_success_until_you_read_it_back():
    service, model, state, reply = run_with_priority("P0")
    assert reply == "Your ticket is open."     # the run reports success
    assert state.failures == []                # the service accepted the call
    assert model.tool_outputs_read == ["Created TCK-1042 with priority P0 (critical)."]
    assert check_stored(service, {"priority": "P1"}) == [
        "TCK-1042 priority: stored 'P0', the request needs 'P1'",
    ]


def test_the_right_value_passes_the_check():
    service, _, state, _ = run_with_priority("P1")
    assert check_stored(service, {"priority": "P1"}) == []
    assert state.writes == ["Created TCK-1042 with priority P1 (high)."]


def test_no_ticket_is_a_failure_too():
    assert check_stored(TicketService(), {"priority": "P1"}) == ["no ticket was stored"]
