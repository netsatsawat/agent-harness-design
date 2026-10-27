"""Pydantic AI 2.61.0: what happens when the 422 repeats on every call, by how the tool reports it.

The companion to check_pydantic_ai_defaults.py (scenarios C1 and C2 there raise once). Here the
scripted model calls create_ticket(priority='high') on every turn, so the tool fails every time,
and the tool reports the failure in one of two ways:

  R1  except ServerValidationError as e: raise ModelRetry(str(e))   (uses the tool's retry budget)
  R2  except ServerValidationError as e: raise ToolFailed(str(e))   (uses no budget)

Everything else is default: Agent retries, UsageLimits. No network, no keys. The model is
pydantic_ai.models.function.FunctionModel. Run from this folder with:

    python -I check_repeat_failure.py > output-repeat-failure.txt
"""

import json
import os
from typing import Any

for k in list(os.environ):
    if k.endswith('_API_KEY') or k in ('OPENAI_BASE_URL', 'ANTHROPIC_BASE_URL'):
        del os.environ[k]
os.environ.update({'OTEL_SDK_DISABLED': 'true', 'DO_NOT_TRACK': '1', 'LOGFIRE_SEND_TO_LOGFIRE': 'false',
                   'PYDANTIC_AI_NO_BANNER': '1'})

import pydantic_ai  # noqa: E402
from pydantic_ai import Agent, ModelRetry, ToolFailed  # noqa: E402
from pydantic_ai.messages import ModelResponse, ToolCallPart  # noqa: E402
from pydantic_ai.models.function import AgentInfo, FunctionModel  # noqa: E402


# --- copied verbatim from part1-loop-and-readback/experiment/servers.py -----------------------------
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
# -------------------------------------------------------------------------------------------------


def run(label: str, wrap: type[Exception]) -> None:
    calls = {'model': 0, 'tool': 0}

    def fn(messages: list, info: AgentInfo) -> ModelResponse:
        calls['model'] += 1
        return ModelResponse(parts=[ToolCallPart('create_ticket', {'title': 'CSV export times out',
                                                                    'priority': 'high'})])

    agent = Agent(FunctionModel(fn))

    @agent.tool_plain
    def create_ticket(title: str, priority: str) -> dict:
        """Create a support ticket."""
        calls['tool'] += 1
        try:
            return ticket_server(title, priority)
        except ServerValidationError as e:
            raise wrap(str(e)) from e

    print(f'\n=== {label}')
    try:
        agent.run_sync('File a high-priority ticket: CSV export times out')
        print('    run outcome: RETURNED to caller')
    except Exception as e:  # noqa: BLE001
        print('    run outcome: EXCEPTION propagated to caller')
        print(f'    exception type: {type(e).__module__}.{type(e).__qualname__}')
        print(f'    exception str : {str(e)}')
    print(f"    model calls made: {calls['model']}   tool executions: {calls['tool']}")


print('python pydantic_ai', pydantic_ai.__version__)
print('ToolFailed importable from pydantic_ai:', ToolFailed.__module__ + '.' + ToolFailed.__qualname__)
run('R1 the 422 every call, tool raises ModelRetry(str(e)), default retries', ModelRetry)
run('R2 the 422 every call, tool raises ToolFailed(str(e)), default UsageLimits', ToolFailed)
