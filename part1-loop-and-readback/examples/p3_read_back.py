"""
Pattern 3: judge a call by the value it stored.

A tool that accepts a call only proves the value was allowed. The ticket service accepts P0 as
easily as P1. After every write, read back the stored value and compare it with the request.

  read_back      the success result of a write: each stored value and its meaning, read from
                 the store, not echoed from the call
  check_stored   the test grader: compare what was stored with the one right value for the task
"""

from __future__ import annotations

from ticket_service import PRIORITIES, TicketService


def read_back(service: TicketService, ticket_id: str) -> str:
    stored = service.get(ticket_id)
    p = stored["priority"]
    return f"Created {ticket_id} with priority {p} ({PRIORITIES.get(p, 'unknown')})."


def check_stored(service: TicketService, expected: dict[str, str]) -> list[str]:
    """Mismatches between every stored ticket and the expected values. An empty list means the
    run stored what the user asked for. A run with no ticket at all is a mismatch too."""
    if not service.tickets:
        return ["no ticket was stored"]
    problems = []
    for ticket in service.tickets.values():
        for name, want in expected.items():
            got = ticket.get(name)
            if got != want:
                problems.append(f"{ticket['id']} {name}: stored {got!r}, the request needs {want!r}")
    return problems
