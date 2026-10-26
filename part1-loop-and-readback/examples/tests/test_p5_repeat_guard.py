"""Pattern 5: an exact repeat of a failed call stops the run and hands off."""

from __future__ import annotations

import asyncio

from agents import Agent, RunConfig, function_tool
from conftest import PROMPT, TITLE

from p1_error_notes import ticket_error_note
from p2_fallback_line import note_or_fixed_line
from p5_repeat_guard import run_with_handoff, stop_repeated_failure
from run_state import RunState, call_key
from scripted_model import Reply, ScriptedModel, ToolCall
from ticket_service import TicketService
from tools import make_create_ticket


def run(model: ScriptedModel) -> tuple[str, RunState, TicketService]:
    service, state = TicketService(), RunState()
    tool = make_create_ticket(service, failure_error_function=ticket_error_note,
                              tool_input_guardrails=[stop_repeated_failure])
    agent = Agent(name="ops", tools=[tool], model=model)
    reply = asyncio.run(run_with_handoff(agent, PROMPT, state,
                                         run_config=RunConfig(tracing_disabled=True)))
    return reply, state, service


def test_an_unchanged_retry_stops_after_one_repeat_and_hands_off():
    stuck = ScriptedModel([ToolCall("create_ticket", {"title": TITLE, "priority": "high"})],
                          repeat_last=True)
    reply, state, service = run(stuck)
    assert len(stuck.inputs) == 2          # one failed call, one repeat, then the guard stops it
    assert len(state.failures) == 1        # the repeat never reached the service
    assert service.tickets == {}
    assert reply == (
        "I could not finish your request. The create_ticket call was rejected because of the "
        "priority, and the next call repeated it unchanged, so I stopped. A person on the team "
        "now has your request and will set the priority."
    )
    assert state.handoffs == [reply]


def test_a_repeat_of_an_error_with_no_field_hands_off_too():
    def lookup_on_call() -> str:
        """Look up the on-call engineer."""
        raise RuntimeError("connection reset by peer")

    stuck = ScriptedModel([ToolCall("lookup_on_call", {})], repeat_last=True)
    state = RunState()
    tool = function_tool(lookup_on_call, failure_error_function=note_or_fixed_line,
                         tool_input_guardrails=[stop_repeated_failure])
    agent = Agent(name="ops", tools=[tool], model=stuck)
    reply = asyncio.run(run_with_handoff(agent, PROMPT, state,
                                         run_config=RunConfig(tracing_disabled=True)))
    assert reply == (
        "I could not finish your request. The lookup_on_call call was rejected, and the next "
        "call repeated it unchanged, so I stopped. A person on the team now has your request "
        "and the error."
    )


def test_a_changed_call_goes_through():
    model = ScriptedModel([
        ToolCall("create_ticket", {"title": TITLE, "priority": "high"}),
        ToolCall("create_ticket", {"title": TITLE, "priority": "urgent"}),
        ToolCall("create_ticket", {"title": TITLE, "priority": "P1"}),
        Reply("Created TCK-1042."),
    ])
    reply, state, service = run(model)
    assert reply == "Created TCK-1042."
    assert len(state.failures) == 2 and state.handoffs == []
    assert service.get("TCK-1042")["priority"] == "P1"


def test_same_values_in_another_order_count_as_a_repeat():
    assert call_key("create_ticket", '{"title": "x", "priority": "high"}') == \
        call_key("create_ticket", '{"priority":"high","title":"x"}')
    assert call_key("create_ticket", '{"priority": "high"}') != \
        call_key("create_ticket", '{"priority": "P1"}')
