"""
The six patterns in one agent: a support agent that opens tickets.

    reply, state = await handle(request, model, TicketService())

model can be any agents Model: ScriptedModel in the tests (no network), or a local Ollama model
in run_ollama.py.
"""

from __future__ import annotations

from agents import Agent, Model, ModelSettings, RunHooks

from p5_repeat_guard import run_with_handoff
from p6_explicit_defaults import (
    RUN_OPTIONS, TOOL_OPTIONS, TOOL_USE_BEHAVIOR, build_run_config, check_sdk_version,
)
from run_state import RunState
from ticket_service import TicketService
from tools import make_create_ticket

INSTRUCTIONS = (
    "You are an operations assistant. Use the create_ticket tool to complete the user's request. "
    "If a tool call returns an error, read it, correct the call, and try again."
)


def build_agent(model: Model, service: TicketService, model_settings: ModelSettings | None = None,
                **tool_overrides) -> Agent[RunState]:
    """tool_overrides replace entries of TOOL_OPTIONS, for example to compare error texts."""
    tool = make_create_ticket(service, **{**TOOL_OPTIONS, **tool_overrides})
    return Agent(
        name="ops", instructions=INSTRUCTIONS, tools=[tool], model=model,
        model_settings=model_settings or ModelSettings(), tool_use_behavior=TOOL_USE_BEHAVIOR,
    )


async def handle(request: str, model: Model, service: TicketService, *,
                 model_settings: ModelSettings | None = None, hooks: RunHooks | None = None,
                 **tool_overrides) -> tuple[str, RunState]:
    check_sdk_version()
    state = RunState()
    agent = build_agent(model, service, model_settings, **tool_overrides)
    reply = await run_with_handoff(
        agent, request, state, run_config=build_run_config(), hooks=hooks, **RUN_OPTIONS,
    )
    return reply, state
