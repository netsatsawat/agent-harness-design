"""
A stand-in model for tests. It plays back a script of tool calls and replies, and keeps every
input the SDK sent it, so a test can read exactly what the model read. No network, no API key.

It runs through the real Agent and Runner, so the SDK's own tool calling, error handling, turn
counting and guardrails all run as they would with a real model.

    model = ScriptedModel([
        ToolCall("create_ticket", {"title": "CSV export times out", "priority": "high"}),
        ToolCall("create_ticket", {"title": "CSV export times out", "priority": "P1"}),
        Reply("Created TCK-1042."),
    ])
    agent = Agent(name="ops", tools=[...], model=model)
    await Runner.run(agent, "Open a high priority ticket ...")
    model.tool_outputs_read   # the text of each tool result, in the order the model read them
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from agents.items import ModelResponse
from agents.models.interface import Model
from agents.usage import Usage
from openai.types.responses import (
    ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText,
)


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class Reply:
    text: str


class ScriptedModel(Model):
    """Returns one scripted step per model call. With repeat_last=True the last step repeats
    for ever, which is how a stuck model behaves."""

    def __init__(self, script: list[ToolCall | Reply], repeat_last: bool = False):
        self.script, self.repeat_last = list(script), repeat_last
        self.inputs: list[Any] = []
        self.tool_outputs_read: list[str] = []

    async def get_response(self, system_instructions, input, model_settings, tools,
                           output_schema, handoffs, tracing, *, previous_response_id=None,
                           conversation_id=None, prompt=None, **kwargs) -> ModelResponse:
        self.inputs.append(input)
        n = len(self.inputs)
        if isinstance(input, list) and input:
            last = input[-1]
            if isinstance(last, dict) and last.get("type") == "function_call_output":
                self.tool_outputs_read.append(str(last.get("output")))
        if n <= len(self.script):
            step = self.script[n - 1]
        elif self.repeat_last and self.script:
            step = self.script[-1]
        else:
            raise RuntimeError(f"the script has no step {n}")
        if isinstance(step, ToolCall):
            out = [ResponseFunctionToolCall(
                id=f"fc_{n}", call_id=f"call_{n}", name=step.name,
                arguments=json.dumps(step.args), type="function_call", status="completed",
            )]
        else:
            out = [ResponseOutputMessage(
                id=f"msg_{n}", role="assistant", status="completed", type="message",
                content=[ResponseOutputText(text=step.text, type="output_text", annotations=[])],
            )]
        return ModelResponse(output=out, usage=Usage(), response_id=None)

    def stream_response(self, *args, **kwargs) -> AsyncIterator[Any]:
        raise NotImplementedError("ScriptedModel does not stream")
