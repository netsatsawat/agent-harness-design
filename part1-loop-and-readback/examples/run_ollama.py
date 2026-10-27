"""
Run the ticket agent (ticket_agent.py, all six patterns) against a real model: a local one served
by Ollama. This is the only example that needs a model. It needs Ollama running on this machine
with the model pulled (ollama pull qwen3.5:4b). No API key, no cost, nothing leaves the machine.

From the part folder:

  .venv/bin/python examples/run_ollama.py --model qwen3.5:4b
  # the same run, but the model reads the SDK's fixed line instead of the approved note
  .venv/bin/python examples/run_ollama.py --model qwen3.5:4b --error-text fixed

It prints every call the model made, the exact text it read back, the reply, and whether the
stored ticket matches the request. Small models at a temperature above 0 vary from run to run,
so change --seed to see other runs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents import (  # noqa: E402
    ModelSettings, OpenAIChatCompletionsModel, RunHooks, set_tracing_disabled,
)
from openai import AsyncOpenAI  # noqa: E402
from openai.types.shared import Reasoning  # noqa: E402

import ticket_agent  # noqa: E402
from p1_error_notes import error_field  # noqa: E402
from p2_fallback_line import FIXED_LINE  # noqa: E402
from p3_read_back import check_stored  # noqa: E402
from run_state import record_failure  # noqa: E402
from ticket_service import TicketService  # noqa: E402

OLLAMA = "http://localhost:11434/v1"
REQUEST = ("Open a high priority ticket: CSV export on the reports page times out for large "
           "date ranges.")


def fixed_line_only(ctx: Any, error: Exception) -> str:
    """The anti-pattern, for comparison: the model reads the fixed line for every error. The
    harness still records which field failed, for the hand-off."""
    return record_failure(ctx, FIXED_LINE, field=error_field(error))


class PrintCalls(RunHooks):
    """Prints each tool call and the exact text the model read back, as the run goes."""

    def __init__(self) -> None:
        self.n = 0

    async def on_tool_end(self, context, agent, tool, result) -> None:
        self.n += 1
        print(f"call {self.n}: {tool.name}({getattr(context, 'tool_arguments', '')})")
        print(f"  model read: {result}")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--model", default="qwen3.5:4b", help="an Ollama model tag")
    ap.add_argument("--error-text", choices=["note", "fixed"], default="note",
                    help="note = the approved note (pattern 1), fixed = the SDK's fixed line")
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--request", default=REQUEST)
    args = ap.parse_args()

    set_tracing_disabled(True)
    client = AsyncOpenAI(base_url=OLLAMA, api_key="ollama")   # Ollama ignores the key
    model = OpenAIChatCompletionsModel(model=args.model, openai_client=client)
    # thinking off (Ollama's /v1 reads reasoning_effort), a seed so a run can be repeated
    settings = ModelSettings(temperature=0.7, max_tokens=800, reasoning=Reasoning(effort="none"),
                             extra_args={"seed": args.seed})
    overrides = {} if args.error_text == "note" else {"failure_error_function": fixed_line_only}

    print(f"model {args.model}, error text: {args.error_text}, seed {args.seed}")
    print(f"request: {args.request}\n")
    service, hooks = TicketService(), PrintCalls()
    reply, state = await ticket_agent.handle(
        args.request, model, service, model_settings=settings, hooks=hooks, **overrides,
    )
    print(f"\nreply: {reply}")
    if state.handoffs:
        print("handed off to a person: yes")
    print("stored:", json.dumps(list(service.tickets.values())))
    problems = check_stored(service, {"priority": "P1"})
    print("check against the request (priority P1):", "ok" if not problems else "; ".join(problems))


if __name__ == "__main__":
    asyncio.run(main())
