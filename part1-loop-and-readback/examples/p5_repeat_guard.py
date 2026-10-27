"""
Pattern 5: stop and hand off when there is no progress.

A model that resends the call that just failed is already stuck, long before the turn limit.
Store each failed call as its tool name plus arguments (run_state.RunState.failures), and check
each new call against them before it runs. A changed call goes through, because a change can be
progress. An exact repeat stops the run and hands off: the user hears what failed and what is
needed, and the request goes to a person.

    tool = function_tool(fn, tool_input_guardrails=[stop_repeated_failure])
    reply = await run_with_handoff(agent, request, RunState())
"""

from __future__ import annotations

from typing import Any

from agents import (
    Agent, Runner, ToolGuardrailFunctionOutput, ToolInputGuardrailData,
    ToolInputGuardrailTripwireTriggered, tool_input_guardrail,
)

from run_state import RunState


@tool_input_guardrail
def stop_repeated_failure(data: ToolInputGuardrailData) -> ToolGuardrailFunctionOutput:
    """Runs before every call of the tool it is attached to."""
    state = data.context.context
    if isinstance(state, RunState):
        before = state.failed_before(data.context.tool_name, data.context.tool_arguments)
        if before is not None:
            return ToolGuardrailFunctionOutput.raise_exception(output_info={
                "tool": before.tool, "arguments": before.arguments, "field": before.field,
                "model_read": before.model_read,
            })
    return ToolGuardrailFunctionOutput.allow()


def hand_off(exc: ToolInputGuardrailTripwireTriggered, state: RunState) -> str:
    """What the user hears when the guard stops a run. The full record goes to state.handoffs,
    where a real system would open a task for a person."""
    info = exc.output.output_info or {}
    field = info.get("field")
    reason = f" because of the {field}" if field else ""
    needed = f" and will set the {field}" if field else " and the error"
    message = (
        f"I could not finish your request. The {info.get('tool', 'tool')} call was rejected"
        f"{reason}, and the next call repeated it unchanged, so I stopped. "
        f"A person on the team now has your request{needed}."
    )
    state.handoffs.append(message)
    return message


async def run_with_handoff(agent: Agent[Any], request: str, state: RunState,
                           **run_kwargs: Any) -> str:
    try:
        result = await Runner.run(agent, request, context=state, **run_kwargs)
    except ToolInputGuardrailTripwireTriggered as exc:
        return hand_off(exc, state)
    return str(result.final_output)
