"""
Pattern 4: limit the loop and write the answer at the limit.

A model that cannot fix a call can keep calling. The OpenAI Agents SDK stops after max_turns
model calls (10 by default) and raises MaxTurnsExceeded, so the user gets no reply. Set the limit
yourself, and add a max_turns entry to error_handlers so the run returns an answer instead:
what was done, what failed and what comes next.

    await Runner.run(agent, request, context=RunState(),
                     max_turns=MAX_TURNS, error_handlers=ERROR_HANDLERS)

This SDK has no cost budget setting, so the turn limit is also what bounds cost.
"""

from __future__ import annotations

from typing import Any

from agents import RunErrorHandlerInput, RunErrorHandlerResult

from run_state import RunState

MAX_TURNS = 6


def at_limit_message(state: RunState, model_calls: int) -> str:
    done = " ".join(state.writes) if state.writes else "Nothing was saved."
    if state.failures:
        tools = ", ".join(sorted({f.tool for f in state.failures}))
        failed = f"{len(state.failures)} tool calls were rejected ({tools})."
    else:
        failed = "No tool call was rejected, but the task did not finish."
    return (
        f"I could not finish your request in {model_calls} steps. Done: {done} "
        f"What failed: {failed} Next: a person on the team has your request and will finish it."
    )


def answer_at_limit(data: RunErrorHandlerInput[Any]) -> RunErrorHandlerResult:
    state = data.context.context if isinstance(data.context.context, RunState) else RunState()
    message = at_limit_message(state, len(data.run_data.raw_responses))
    state.handoffs.append(message)
    # include_in_history=False keeps this answer out of the conversation the model sees next time
    return RunErrorHandlerResult(final_output=message, include_in_history=False)


ERROR_HANDLERS = {"max_turns": answer_at_limit}
