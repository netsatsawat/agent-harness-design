"""The six patterns together, on the three ways a run can go."""

from __future__ import annotations

import asyncio

from conftest import PROMPT, TITLE

import ticket_agent
from p3_read_back import check_stored
from p4_turn_limit import MAX_TURNS
from scripted_model import Reply, ScriptedModel, ToolCall
from ticket_service import TicketService


def handle(model):
    service = TicketService()
    reply, state = asyncio.run(ticket_agent.handle(PROMPT, model, service))
    return reply, state, service


def test_the_model_fixes_the_call_from_the_note():
    model = ScriptedModel([
        ToolCall("create_ticket", {"title": TITLE, "priority": "high"}),
        ToolCall("create_ticket", {"title": TITLE, "priority": "P1"}),
        Reply("Created TCK-1042 with priority P1 (high)."),
    ])
    reply, state, service = handle(model)
    assert check_stored(service, {"priority": "P1"}) == []
    assert state.writes == ["Created TCK-1042 with priority P1 (high)."]
    assert state.handoffs == []


def test_a_stuck_model_is_handed_off_after_one_repeat():
    stuck = ScriptedModel([ToolCall("create_ticket", {"title": TITLE, "priority": "high"})],
                          repeat_last=True)
    reply, state, service = handle(stuck)
    assert len(stuck.inputs) == 2
    assert reply.startswith("I could not finish your request. The create_ticket call was rejected")
    assert service.tickets == {} and len(state.handoffs) == 1


def test_a_model_that_keeps_changing_the_value_stops_at_the_limit_with_an_answer():
    values = ["high", "urgent", "High", "HIGH", "1", "p1", "top", "important"]
    model = ScriptedModel([ToolCall("create_ticket", {"title": TITLE, "priority": v})
                           for v in values])
    reply, state, service = handle(model)
    assert len(model.inputs) == MAX_TURNS
    assert reply.startswith(f"I could not finish your request in {MAX_TURNS} steps.")
    assert service.tickets == {} and len(state.handoffs) == 1
