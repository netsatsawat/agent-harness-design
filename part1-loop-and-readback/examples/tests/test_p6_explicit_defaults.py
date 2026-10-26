"""
Pattern 6: tests that fail as soon as a default changes.

The strings below are typed out in full on purpose, not imported from the code under test, so
a change to the note, to the fixed line or to the SDK's own default fails a test.
"""

from __future__ import annotations

import asyncio
import importlib.metadata

from agents import Agent, RunConfig, Runner
from agents.run_config import DEFAULT_MAX_TURNS
from agents.tool import default_tool_error_function
from conftest import PROMPT, TITLE

import ticket_agent
from p1_error_notes import run_wide_formatter
from p2_fallback_line import FIXED_LINE
from p6_explicit_defaults import SDK_VERSION, TOOL_OPTIONS, build_run_config
from scripted_model import Reply, ScriptedModel, ToolCall
from ticket_service import TicketService
from tools import make_create_ticket

PRIORITY_NOTE = (
    "priority is not valid. Allowed values: P0 (critical), P1 (high), P2 (normal). "
    "Next step: call create_ticket again with priority set to one of these codes."
)
SDK_FIXED_LINE = "An error occurred while running the tool. Please try again."


def fails_once() -> ScriptedModel:
    return ScriptedModel([
        ToolCall("create_ticket", {"title": TITLE, "priority": "high"}),
        ToolCall("create_ticket", {"title": TITLE, "priority": "P1"}),
        Reply("Done."),
    ])


def test_the_pinned_sdk_is_installed():
    assert importlib.metadata.version("openai-agents") == SDK_VERSION


def test_our_harness_sends_the_exact_note_after_a_failure():
    model = fails_once()
    reply, state = asyncio.run(ticket_agent.handle(PROMPT, model, TicketService()))
    assert model.tool_outputs_read == [
        PRIORITY_NOTE, "Created TCK-1042 with priority P1 (high).",
    ]
    assert reply == "Done."


def test_the_sdk_default_error_text_has_not_changed():
    # what a tool with no handler of its own sends the model on this SDK version
    model = fails_once()
    agent = Agent(name="ops", tools=[make_create_ticket(TicketService())], model=model)
    asyncio.run(Runner.run(agent, PROMPT, run_config=RunConfig(tracing_disabled=True)))
    assert model.tool_outputs_read[0] == SDK_FIXED_LINE
    assert default_tool_error_function(None, RuntimeError("x")) == SDK_FIXED_LINE
    # our own copy matches today. If the SDK changes its line, ours stays and this test says so
    assert FIXED_LINE == SDK_FIXED_LINE


def test_the_sdk_default_turn_limit_has_not_changed():
    # this harness sets its own limit, but a change here means the release notes need a read
    assert DEFAULT_MAX_TURNS == 10


def test_a_tool_with_its_own_handler_ignores_the_run_wide_formatter():
    # Passing failure_error_function, even the SDK's own default function, turns off
    # RunConfig.tool_error_formatter for that tool. Set both on purpose, not by accident.
    model = fails_once()
    tool = make_create_ticket(TicketService(), failure_error_function=default_tool_error_function)
    agent = Agent(name="ops", tools=[tool], model=model)
    asyncio.run(Runner.run(agent, PROMPT, run_config=RunConfig(
        tracing_disabled=True, tool_error_formatter=run_wide_formatter)))
    assert model.tool_outputs_read[0] == SDK_FIXED_LINE


def test_every_default_this_harness_relies_on_is_set_in_code():
    assert set(TOOL_OPTIONS) >= {"failure_error_function", "needs_approval", "strict_mode"}
    config = build_run_config()
    assert config.tool_error_formatter is run_wide_formatter
    assert config.tracing_disabled is True
