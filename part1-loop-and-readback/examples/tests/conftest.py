"""Shared test setup: no tracing upload, no network, no API key."""

from __future__ import annotations

import pytest
from agents import set_tracing_disabled

PROMPT = "Open a high priority ticket: CSV export on the reports page times out for large date ranges."
TITLE = "CSV export on reports page times out for large date ranges"


@pytest.fixture(autouse=True, scope="session")
def _no_tracing():
    set_tracing_disabled(True)
    yield
