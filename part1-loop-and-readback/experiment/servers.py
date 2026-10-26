"""
The two fake servers the tools call, and the error their API client raises.

Pure Python with no SDK import, so check_error_strings.py can load it under both the current
SDK venv (.venv) and the old one (.venv-0.22.3).

Each server validates the way a FastAPI + pydantic service does and answers HTTP 422 with
pydantic's error body. ServerValidationError puts that whole body in str(error), the way SDK
clients such as Twilio's or Stripe's carry the server's message. That is the generous case for
the old 0.22.3 default, which pasted str(error) into what the model reads. A client that calls
httpx/requests raise_for_status() would carry only the status line and the URL, and the old
default would then have shown no allowed values at all.
"""

from __future__ import annotations

import json
import re
from typing import Any

E164_PATTERN = r"^\+[1-9]\d{1,14}$"


class ServerValidationError(Exception):
    """What the API client raises on HTTP 422, with a FastAPI/pydantic-style body."""

    def __init__(self, field_name: str, value: Any, err_type: str, msg: str,
                 ctx: dict | None = None):
        self.field_name, self.value = field_name, value
        detail = {"type": err_type, "loc": ["body", field_name], "msg": msg, "input": value}
        if ctx:
            detail["ctx"] = ctx
        super().__init__(f"422 Unprocessable Entity: {json.dumps({'detail': [detail]})}")


def ticket_server(title: str, priority: str) -> dict:
    """Accepts only the codes P0 (critical), P1 (high), P2 (normal)."""
    if priority not in ("P0", "P1", "P2"):
        raise ServerValidationError(
            "priority", priority, "enum", "Input should be 'P0', 'P1' or 'P2'",
            {"expected": "'P0', 'P1' or 'P2'"},
        )
    return {"id": "TCK-1042", "title": title, "priority": priority, "status": "open"}


def sms_server(to: str, message: str) -> dict:
    """Accepts only E.164 numbers: a plus sign, the country code, then digits."""
    if not re.fullmatch(r"\+[1-9][0-9]{1,14}", to or ""):
        raise ServerValidationError(
            "to", to, "string_pattern_mismatch",
            f"String should match pattern '{E164_PATTERN}'", {"pattern": E164_PATTERN},
        )
    if not (message or "").strip():
        raise ServerValidationError(
            "message", message, "string_too_short", "String should have at least 1 character",
            {"min_length": 1},
        )
    return {"sid": "SM-8812", "to": to, "status": "queued"}
