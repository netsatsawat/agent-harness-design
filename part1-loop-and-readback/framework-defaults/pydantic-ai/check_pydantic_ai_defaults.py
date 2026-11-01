"""What does a Pydantic AI agent's model read after a tool fails, with every default left alone?

No network, no API keys, no model calls. The model is pydantic_ai.models.function.FunctionModel,
the framework's own scripted test model, so the real Agent loop (graph, tool manager, retries,
usage limits) runs unchanged. Run from this folder with:

    python -I check_pydantic_ai_defaults.py > output.txt

Scenarios
  A  tool raises the Part 1 ServerValidationError (all defaults)                -> F1
  B  model sends arguments that fail the tool's own schema (priority=123)      -> F1b
  B2 model omits a required argument (no priority)                             -> F1b
  B3 model keeps sending bad arguments (default tool retry budget)             -> F6
  C1 tool converts the exception to ModelRetry itself (per-tool knob)         -> F2
  C2 tool converts the exception to ToolFailed itself (per-tool knob)         -> F2
  C3 one capability converts every tool exception (global knob)               -> F2
  D  model calls a working tool forever (default UsageLimits)                 -> F3, F4
  E  tool declared requires_approval=True                                     -> F5
"""

import dataclasses
import json
import os
import sys
from typing import Any

for k in list(os.environ):
    if k.endswith('_API_KEY') or k in ('OPENAI_BASE_URL', 'ANTHROPIC_BASE_URL'):
        del os.environ[k]
os.environ.update({'OTEL_SDK_DISABLED': 'true', 'DO_NOT_TRACK': '1', 'LOGFIRE_SEND_TO_LOGFIRE': 'false',
                   'PYDANTIC_AI_NO_BANNER': '1'})

import pydantic_ai  # noqa: E402
from pydantic_ai import Agent, DeferredToolRequests, ModelRetry, ToolFailed, capture_run_messages  # noqa: E402
from pydantic_ai.capabilities import AbstractCapability  # noqa: E402
from pydantic_ai.messages import (  # noqa: E402
    ERROR_OUTCOMES, ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart,
)
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


def create_ticket(title: str, priority: str) -> dict:
    """Create a support ticket."""
    return ticket_server(title, priority)


def scripted_model(turn1_args: dict, *, repeat_bad: bool = False):
    """Turn 1 calls create_ticket(**turn1_args). Later turns record what arrived and answer in text."""
    seen: list[list] = []

    def fn(messages: list, info: AgentInfo) -> ModelResponse:
        seen.append(list(messages))
        if len(seen) == 1 or repeat_bad:
            return ModelResponse(parts=[ToolCallPart('create_ticket', dict(turn1_args))])
        return ModelResponse(parts=[TextPart('ok')])

    return FunctionModel(fn), seen


def describe_last_request(messages: list) -> dict:
    """The tool-result parts the model got in the newest request, plus how providers render them."""
    req = messages[-1]
    assert isinstance(req, ModelRequest)
    out = []
    for p in req.parts:
        d: dict[str, Any] = {'part_type': type(p).__name__}
        if isinstance(p, ToolReturnPart):
            d.update(
                tool_name=p.tool_name,
                outcome=p.outcome,
                content=p.content,
                retry=repr(p.retry),
                # OpenAI Chat Completions sends this as the role="tool" content (models/openai.py
                # calls model_response_str_and_user_content() with the default wrap_if_error=True).
                openai_chat_role_tool_content=p.model_response_str(),
                # Providers with a native error channel (Anthropic is_error, Bedrock status) send the
                # unwrapped text and set the flag from `outcome in ERROR_OUTCOMES`.
                native_channel_text=p.model_response_str(wrap_if_error=False),
                native_error_flag=p.outcome in ERROR_OUTCOMES,
            )
        else:
            d['repr'] = repr(p)
        out.append(d)
    return {'kind': type(req).__name__, 'parts': out}


def run(label: str, agent: Agent, seen: list, **kw) -> dict:
    result: dict[str, Any] = {'scenario': label}
    with capture_run_messages() as history:
        try:
            r = agent.run_sync('Open a high-priority ticket: CSV export times out', **kw)
            result['run_outcome'] = 'returned'
            result['output'] = repr(r.output)
            result['usage_requests'] = r.usage.requests
        except Exception as e:  # noqa: BLE001 - we want to see whatever escapes the loop
            result['run_outcome'] = 'raised'
            result['exception_type'] = f'{type(e).__module__}.{type(e).__qualname__}'
            result['exception_message'] = str(e)
            if e.__cause__ is not None:
                result['exception_cause'] = f'{type(e.__cause__).__qualname__}: {e.__cause__}'
    result['model_calls'] = len(seen)
    parts = [
        f'{type(m).__name__}:' + ','.join(
            type(p).__name__ + (f'[{p.outcome}]' if isinstance(p, ToolReturnPart) else '') for p in m.parts
        )
        for m in history
    ]
    if len(parts) > 8:  # keep the long loop readable: first 3, a count, last 3
        parts = parts[:3] + [f'... {len(parts) - 6} more messages ...'] + parts[-3:]
    result['history_messages'] = len(history)
    result['history_parts'] = parts
    if len(seen) >= 2:
        result['turn2_model_received'] = describe_last_request(seen[1])
    return result


def main() -> None:
    results = []
    print(f'python {sys.version.split()[0]}  pydantic_ai {pydantic_ai.__version__}')

    # A: all defaults, tool raises the Part 1 exception.
    model, seen = scripted_model({'title': 'CSV export times out', 'priority': 'high'})
    agent = Agent(model)
    agent.tool_plain(create_ticket)
    results.append(run('A_default_tool_raises_ServerValidationError', agent, seen))

    # B: argument fails the tool's own schema (int where str is declared).
    model, seen = scripted_model({'title': 'CSV export times out', 'priority': 123})
    agent = Agent(model)
    agent.tool_plain(create_ticket)
    results.append(run('B_bad_args_priority_int', agent, seen))

    # B2: required argument missing.
    model, seen = scripted_model({'title': 'CSV export times out'})
    agent = Agent(model)
    agent.tool_plain(create_ticket)
    results.append(run('B2_missing_priority', agent, seen))

    # B3: model never fixes its arguments -> default per-tool retry budget.
    model, seen = scripted_model({'title': 'CSV export times out', 'priority': 123}, repeat_bad=True)
    agent = Agent(model)
    agent.tool_plain(create_ticket)
    results.append(run('B3_bad_args_every_turn', agent, seen))

    # C1: per-tool knob, the tool turns its own exception into ModelRetry.
    model, seen = scripted_model({'title': 'CSV export times out', 'priority': 'high'})
    agent = Agent(model)

    @agent.tool_plain(name='create_ticket')
    def create_ticket_modelretry(title: str, priority: str) -> dict:
        try:
            return ticket_server(title, priority)
        except ServerValidationError as e:
            raise ModelRetry(str(e)) from e

    results.append(run('C1_tool_raises_ModelRetry_with_exception_text', agent, seen))

    # C2: per-tool knob, the tool reports a terminal failure with ToolFailed.
    model, seen = scripted_model({'title': 'CSV export times out', 'priority': 'high'})
    agent = Agent(model)

    @agent.tool_plain(name='create_ticket')
    def create_ticket_toolfailed(title: str, priority: str) -> dict:
        try:
            return ticket_server(title, priority)
        except ServerValidationError as e:
            raise ToolFailed(str(e)) from e

    results.append(run('C2_tool_raises_ToolFailed_with_exception_text', agent, seen))

    # C3: global knob, one capability rewrites every tool exception into a note for the model.
    class ToolErrorsToModel(AbstractCapability[Any]):
        async def on_tool_execute_error(self, ctx, *, call, tool_def, args, error):
            raise ToolFailed(f'{call.tool_name} failed: {error}')

    model, seen = scripted_model({'title': 'CSV export times out', 'priority': 'high'})
    agent = Agent(model, capabilities=[ToolErrorsToModel()])
    agent.tool_plain(create_ticket)
    results.append(run('C3_capability_on_tool_execute_error', agent, seen))

    # D: a working tool called forever, default UsageLimits.
    calls = {'n': 0}

    def loop_fn(messages: list, info: AgentInfo) -> ModelResponse:
        calls['n'] += 1
        return ModelResponse(parts=[ToolCallPart('ping', {})])

    agent = Agent(FunctionModel(loop_fn))

    @agent.tool_plain
    def ping() -> str:
        return 'pong'

    d = run('D_tool_called_forever_default_limits', agent, [])
    d['model_calls'] = calls['n']
    lim = pydantic_ai.usage.UsageLimits()
    d['default_UsageLimits'] = {f.name: getattr(lim, f.name) for f in dataclasses.fields(lim)}
    results.append(d)

    # E: approval. First with the default output type, then with DeferredToolRequests allowed.
    for label, kwargs in (('E1_requires_approval_default_output_type', {}),
                          ('E2_requires_approval_output_DeferredToolRequests',
                           {'output_type': [str, DeferredToolRequests]})):
        model, seen = scripted_model({'title': 'CSV export times out', 'priority': 'P1'})
        agent = Agent(model, **kwargs)
        ran = {'n': 0}

        @agent.tool_plain(requires_approval=True, name='create_ticket')
        def create_ticket_gated(title: str, priority: str) -> dict:
            ran['n'] += 1
            return ticket_server(title, priority)

        e = run(label, agent, seen)
        e['tool_body_executed'] = ran['n']
        results.append(e)

    print(json.dumps(results, indent=2, default=str))


if __name__ == '__main__':
    main()
