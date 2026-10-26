"""
Pattern 2: send approved text instead of the raw exception.

Raw exception text can carry connection strings, internal URLs and customer data, and it can give
codes without their meaning. Send the model only approved text, and keep the full exception in
your own logs.

  note_or_fixed_line   a failure_error_function: the approved note when there is one.
                       Otherwise the fixed line plus a log entry with the full exception, so
                       someone writes the missing note
  unsafe_findings      the check: search a tool result for stack frames, file paths, internal
                       URLs, credentials and raw HTTP bodies
"""

from __future__ import annotations

import logging
import re
from typing import Any

from agents import RunContextWrapper

from p1_error_notes import approved_note, error_field
from run_state import record_failure

# Your own copy of the fixed line, so an SDK upgrade cannot change it (see p6_explicit_defaults.py).
FIXED_LINE = "An error occurred while running the tool. Please try again."

missing_note_log = logging.getLogger("harness.missing_note")


def note_or_fixed_line(ctx: RunContextWrapper[Any], error: Exception) -> str:
    note = approved_note(error)
    if note is None:
        missing_note_log.warning(
            "no approved note for %s from tool %s, so the model read the fixed line",
            type(error).__name__, getattr(ctx, "tool_name", "?"), exc_info=error,
        )
        note = FIXED_LINE
    return record_failure(ctx, note, field=error_field(error))


UNSAFE = {
    "stack trace": re.compile(r'Traceback \(most recent call last\)|File "[^"]+", line \d+'),
    "file path": re.compile(r'(?:^|[\s"\'(=])(?:/[\w.-]+){2,}|[A-Za-z]:\\[\w.\\-]+'),
    "internal URL": re.compile(
        r"https?://(?:localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}"
        r"|[\w.-]+\.(?:internal|local|corp))\b"),
    "credential in URL": re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:@/]+:[^\s@/]+@"),
    "token": re.compile(
        r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{8,}|\bgh[pousr]_[A-Za-z0-9]{8,}|\bxox[abprs]-[\w-]{8,}"
        r"|\bBearer\s+[\w.~+/-]{8,}"),
    "raw HTTP body": re.compile(r"\b[1-5]\d\d [A-Z][A-Za-z ]+:\s*[\[{]|\"detail\"\s*:"),
}


def unsafe_findings(text: str) -> list[str]:
    """The kinds of unsafe content found in a tool result, empty when it looks safe."""
    return [kind for kind, pattern in UNSAFE.items() if pattern.search(text or "")]
