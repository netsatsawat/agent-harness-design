"""
The one tool the examples use: create_ticket, built around a TicketService.

The schema is deliberately vague ("Priority for the ticket."), the way many real tool schemas
are, so a model often sends "high" on its first call and the service rejects it. Each pattern
then decides what the model reads back.

The success result is the read-back line from p3_read_back.py: the stored value and its meaning.
"""

from __future__ import annotations

from typing import Any

from agents import FunctionTool, RunContextWrapper, function_tool

from p3_read_back import read_back
from run_state import RunState
from ticket_service import TicketService


def make_create_ticket(service: TicketService, **tool_options: Any) -> FunctionTool:
    """Build create_ticket for this service. tool_options go straight to function_tool, for
    example failure_error_function=... or tool_input_guardrails=[...]."""

    def create_ticket(ctx: RunContextWrapper[Any], title: str, priority: str) -> str:
        """Create a support ticket.

        Args:
            title: Short summary of the issue.
            priority: Priority for the ticket.
        """
        ticket_id = service.create(title, priority)
        line = read_back(service, ticket_id)
        if isinstance(ctx.context, RunState):
            ctx.context.writes.append(line)
        return line

    return function_tool(create_ticket, **tool_options)
