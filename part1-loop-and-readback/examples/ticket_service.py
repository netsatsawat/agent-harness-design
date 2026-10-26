"""
A made-up ticket service with the validation a real one has. No network, no model.

The service accepts only the priority codes P0, P1 and P2. On a bad value it raises the error an
API client raises on HTTP 422, with a FastAPI/pydantic-style body in str(error). Like many real
services, that body lists the codes but not what they mean.
"""

from __future__ import annotations

import json

PRIORITIES = {"P0": "critical", "P1": "high", "P2": "normal"}


class ValidationError(Exception):
    """What the service's API client raises on HTTP 422."""

    def __init__(self, field: str, value: object, msg: str):
        self.field, self.value = field, value
        body = {"detail": [{"loc": ["body", field], "msg": msg, "input": value}]}
        super().__init__(f"422 Unprocessable Entity: {json.dumps(body)}")


class TicketService:
    """An in-memory ticket store. create() validates and saves a ticket, and get() reads it back."""

    def __init__(self) -> None:
        self.tickets: dict[str, dict] = {}
        self._next_id = 1042

    def create(self, title: str, priority: str) -> str:
        if not (title or "").strip():
            raise ValidationError("title", title, "String should have at least 1 character")
        if priority not in PRIORITIES:
            raise ValidationError("priority", priority, "Input should be 'P0', 'P1' or 'P2'")
        ticket_id = f"TCK-{self._next_id}"
        self._next_id += 1
        self.tickets[ticket_id] = {"id": ticket_id, "title": title.strip(), "priority": priority}
        return ticket_id

    def get(self, ticket_id: str) -> dict:
        return dict(self.tickets[ticket_id])
