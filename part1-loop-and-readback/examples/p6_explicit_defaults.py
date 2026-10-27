"""
Pattern 6: treat framework defaults as design decisions.

A default is a choice someone made for a different agent, and an upgrade can change it. The
SDK's tool error text did: up to 0.22.3 the model read the raw exception, and since 0.23.1 it
reads one fixed line. List the defaults this harness relies on and set each one here, even when
it matches the current default, so an upgrade cannot change it without a failing test.

  SDK_VERSION     the pinned version (requirements.lock.txt). Read the release notes for the
                  names below before changing it
  TOOL_OPTIONS    passed to function_tool for every tool
  build_run_config()  passed to Runner.run

The test that goes with it is tests/test_p6_explicit_defaults.py: it makes a tool fail on purpose
and asserts the exact text the model reads.
"""

from __future__ import annotations

import importlib.metadata
from typing import Any

from agents import RunConfig

from p1_error_notes import run_wide_formatter
from p2_fallback_line import note_or_fixed_line
from p4_turn_limit import ERROR_HANDLERS, MAX_TURNS
from p5_repeat_guard import stop_repeated_failure

SDK_VERSION = "0.24.0"

# Every tool: our own error text, no approval step, strict JSON schema, the repeat guard.
TOOL_OPTIONS: dict[str, Any] = {
    "failure_error_function": note_or_fixed_line,   # SDK default: its fixed line
    "needs_approval": False,                         # SDK default: False
    "strict_mode": True,                             # SDK default: True
    "tool_input_guardrails": [stop_repeated_failure],
}

# Every run: the turn limit and the answer at the limit (SDK default: 10 turns, then raise).
RUN_OPTIONS: dict[str, Any] = {"max_turns": MAX_TURNS, "error_handlers": ERROR_HANDLERS}

# The Agent: call the model again after each tool result (SDK default: "run_llm_again").
TOOL_USE_BEHAVIOR = "run_llm_again"


def build_run_config() -> RunConfig:
    return RunConfig(
        # formats errors for any tool left on the SDK default handler. A tool with its own
        # failure_error_function (every tool built with TOOL_OPTIONS) keeps that one
        tool_error_formatter=run_wide_formatter,   # SDK default: None
        tool_not_found_behavior="raise_error",     # SDK default: "raise_error"
        # tracing is on by default and uploads traces to OpenAI, and these examples run offline
        tracing_disabled=True,                     # SDK default: False
    )


def check_sdk_version() -> None:
    installed = importlib.metadata.version("openai-agents")
    if installed != SDK_VERSION:
        raise RuntimeError(
            f"openai-agents {installed} is installed, but this harness was checked on "
            f"{SDK_VERSION}. Read its release notes for tool errors, max_turns, approvals and "
            f"tracing, run the tests, then update SDK_VERSION."
        )
