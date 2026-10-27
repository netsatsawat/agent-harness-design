"""
What does the Claude Agent SDK (Python) hand the model when a custom tool raises?

claude-agent-sdk 0.2.174 (bundles Claude Code CLI 2.1.310). No network, no API key, no model.

The agent loop itself (model call -> tool call -> tool_result -> next model call) runs inside
the bundled Claude Code CLI, a closed-source binary. This script does not start it. It runs the
SDK's own side of the loop for real and stands in for the CLI at the transport boundary:

  1. Defaults: ClaudeAgentOptions() field values, and the CLI argv the SDK's real
     SubprocessCLITransport._build_command() would pass with those defaults (built, not run).
  2. The in-process MCP server: the exact JSON-RPC tools/call result the SDK's
     create_sdk_mcp_server returns for the raising tool, driven through the SDK's own
     SdkMcpBridge with the same raw JSON-RPC dicts the CLI sends.
  3. The real query() loop with ALL options left at defaults except mcp_servers (needed to
     register the tool), over a scripted fake CLI transport (Transport is the SDK's documented
     extension point for custom transports). The fake CLI plays turn 1 of the model: it calls
     create_ticket(title="CSV export times out", priority="high"). It captures the SDK's real
     mcp_response, then builds the tool_result the model reads on turn 2 the way the bundled CLI
     2.1.310 does (joined text blocks, is_error true). That last step is a reconstruction from
     the CLI source, labelled as such in the output.
  4. Bad arguments: priority=123 and a missing priority, through the same server.
  5. Turn limit boundary: what query() does when the CLI ends a run with error_max_turns and
     exits non-zero (the SDK's real ResultError path; the result frame shape is copied from the
     CLI source).

Run from this folder with:

    python -I check_claude_agent_sdk_defaults.py > output.txt
"""

from __future__ import annotations

import importlib.metadata
import json
import os
from typing import Any

# No keys, no telemetry. Nothing here calls a provider, but make sure of it.
for _k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN",
           "OPENAI_API_KEY", "ANTHROPIC_BASE_URL"):
    os.environ.pop(_k, None)
os.environ.update({"DO_NOT_TRACK": "1", "OTEL_SDK_DISABLED": "true",
                   "DISABLE_TELEMETRY": "1", "CLAUDE_AGENT_SDK_SKIP_VERSION_CHECK": "1"})

import anyio  # noqa: E402
import anyio.abc  # noqa: E402
import mcp.types  # noqa: E402

import claude_agent_sdk as sdk  # noqa: E402
from claude_agent_sdk._cli_version import __cli_version__  # noqa: E402
from claude_agent_sdk import (  # noqa: E402
    AssistantMessage, ClaudeAgentOptions, ResultError, ResultMessage, TextBlock,
    ToolResultBlock, ToolUseBlock, Transport, UserMessage, create_sdk_mcp_server, query, tool,
)
from claude_agent_sdk._errors import ProcessError  # noqa: E402
from claude_agent_sdk._internal.sdk_mcp_bridge import SdkMcpBridge  # noqa: E402
from claude_agent_sdk._internal.transport.subprocess_cli import (  # noqa: E402
    SubprocessCLITransport,
)
from claude_agent_sdk.types import _configure_can_use_tool  # noqa: E402

# ---------------------------------------------------------------------------------------------
# Copied verbatim from agent-harness-design/part1-loop-and-readback/experiment/servers.py
# ---------------------------------------------------------------------------------------------


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


# The tool, defined the way the docs show: priority is a plain string, so "high" passes the
# tool's own schema and fails at the ticket service, exactly like the Part 1 experiment.
@tool("create_ticket", "Create a support ticket.", {"title": str, "priority": str})
async def create_ticket(args: dict[str, Any]) -> dict[str, Any]:
    result = ticket_server(**args)  # raises ServerValidationError for priority "high"
    return {"content": [{"type": "text", "text": json.dumps(result)}]}


SERVER_NAME = "tickets"
FULL_TOOL_NAME = f"mcp__{SERVER_NAME}__create_ticket"
TURN1_ARGS = {"title": "CSV export times out", "priority": "high"}


def hr(title: str) -> None:
    print("\n" + "=" * 92 + f"\n{title}\n" + "=" * 92)


def show(label: str, value: Any) -> None:
    text = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False)
    print(f"{label}:\n{text}")


def cli_tool_result_from_mcp(mcp_result: dict[str, Any], tool_use_id: str) -> dict[str, Any]:
    """The tool_result block Claude Code CLI 2.1.310 builds from an MCP tools/call result.

    Reconstructed from the bundled CLI's own source (strings in _bundled/claude):
      - on isError it joins the text blocks with "\\n" (or "Unknown error" if none) and throws
        McpToolCallError(text, "MCP tool returned error");
      - the tool executor catches it and yields
        {type: "tool_result", content: <error message>, is_error: true, tool_use_id}.
    Success results go through the MCP tool's mapToolResultToToolResultBlockParam instead; the
    success shape is not modelled here.
    """
    if mcp_result.get("isError"):
        texts = [str(b["text"]) for b in mcp_result.get("content", []) if "text" in b]
        message = "\n".join(texts) if texts else "Unknown error"
        return {"type": "tool_result", "content": message, "is_error": True,
                "tool_use_id": tool_use_id}
    return {"type": "tool_result", "content": mcp_result.get("content"),
            "tool_use_id": tool_use_id}


# ---------------------------------------------------------------------------------------------
# 1. Defaults
# ---------------------------------------------------------------------------------------------


def section_defaults() -> None:
    hr("1. DEFAULTS: ClaudeAgentOptions() and the CLI argv the SDK builds from it (not run)")
    print(f"claude_agent_sdk.__version__ = {sdk.__version__}")
    print(f"bundled Claude Code CLI      = {__cli_version__}")
    print(f"mcp package                  = {importlib.metadata.version('mcp')}")
    o = ClaudeAgentOptions()
    for name in ("max_turns", "max_budget_usd", "task_budget", "permission_mode",
                 "can_use_tool", "permission_prompt_tool_name", "allowed_tools", "hooks"):
        print(f"ClaudeAgentOptions().{name:<28} = {getattr(o, name)!r}")

    def argv_for(opts: ClaudeAgentOptions) -> list[str]:
        t = SubprocessCLITransport(prompt="x", options=_configure_can_use_tool(opts))
        t._cli_path = "claude"  # resolved at connect(); set by hand so nothing is spawned
        return t._build_command()

    watched = ("--max-turns", "--max-budget-usd", "--task-budget", "--permission-mode",
               "--permission-prompt-tool", "--allowedTools")

    def summarise(label: str, argv: list[str]) -> None:
        found = {f: argv[argv.index(f) + 1] for f in watched if f in argv}
        print(f"{label}: limit/approval flags passed to the CLI = {found or 'none'}")

    summarise("defaults (+ mcp_servers only)  ",
              argv_for(ClaudeAgentOptions(mcp_servers={SERVER_NAME: create_sdk_mcp_server(
                  SERVER_NAME, tools=[create_ticket])})))

    async def _allow(*_a: Any) -> Any:  # a callback is enough to switch approvals to the SDK
        return sdk.PermissionResultAllow()

    summarise("max_turns=5, max_budget_usd=1.0 ",
              argv_for(ClaudeAgentOptions(max_turns=5, max_budget_usd=1.0)))
    summarise("can_use_tool=<callback>         ", argv_for(ClaudeAgentOptions(can_use_tool=_allow)))
    summarise("allowed_tools=[the tool]        ",
              argv_for(ClaudeAgentOptions(allowed_tools=[FULL_TOOL_NAME])))


# ---------------------------------------------------------------------------------------------
# 2. + 4. The in-process MCP server, called the way the CLI calls it
# ---------------------------------------------------------------------------------------------


async def section_mcp_server() -> None:
    hr("2. IN-PROCESS MCP SERVER: raw JSON-RPC tools/call through the SDK's own SdkMcpBridge")
    server = create_sdk_mcp_server(SERVER_NAME, tools=[create_ticket])
    bridge = SdkMcpBridge(SERVER_NAME, server["instance"])
    try:
        init = await bridge.handle({
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {"protocolVersion": mcp.types.LATEST_PROTOCOL_VERSION, "capabilities": {},
                       "clientInfo": {"name": "fake-claude-code", "version": "0"}}})
        print(f"initialize ok: serverInfo={init['result']['serverInfo']}")
        await bridge.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
        listed = await bridge.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        show("tools/list inputSchema the model is given",
             listed["result"]["tools"][0]["inputSchema"])

        cases = [
            ("A. server raises ServerValidationError (priority='high')", TURN1_ARGS),
            ("B. bad args vs the tool's own schema (priority=123)",
             {"title": "CSV export times out", "priority": 123}),
            ("C. bad args vs the tool's own schema (priority missing)",
             {"title": "CSV export times out"}),
            ("D. control: valid call (priority='P1')",
             {"title": "CSV export times out", "priority": "P1"}),
        ]
        for i, (label, args) in enumerate(cases, start=2):
            resp = await bridge.handle({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                                        "params": {"name": "create_ticket", "arguments": args}})
            print(f"\n--- {label}")
            print(f"arguments: {json.dumps(args)}")
            print("raised to the caller: no (the bridge returned a JSON-RPC response)")
            show("JSON-RPC response (verbatim)", resp)
            if label.startswith("A."):
                exc_text = str(ServerValidationError(
                    "priority", "high", "enum", "Input should be 'P0', 'P1' or 'P2'",
                    {"expected": "'P0', 'P1' or 'P2'"}))
                text = resp["result"]["content"][0]["text"]
                print(f"text == str(exception): {text == exc_text}")
    finally:
        await bridge.aclose()


# ---------------------------------------------------------------------------------------------
# 3. + 5. The real query() loop over a scripted fake CLI transport
# ---------------------------------------------------------------------------------------------


class FakeClaudeCode(Transport):
    """Stands in for the Claude Code CLI on the other end of the SDK's stdio protocol.

    mode="tool_error": turn 1 = the fake model calls create_ticket(priority="high"); the fake CLI
    asks the SDK to run it (mcp_message control request), captures the SDK's answer, builds the
    turn-2 tool_result the way CLI 2.1.310 does, then ends the turn with a success result.

    mode="max_turns": the fake CLI ends the run the way the CLI does at --max-turns: an
    error_max_turns result frame, then a non-zero exit (ProcessError from the transport).
    """

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self._send, self._recv = anyio.create_memory_object_stream[dict](100)
        self._pending: dict[str, anyio.Event] = {}
        self._answers: dict[str, dict] = {}
        self._n = 0
        self._ready = False
        self._tg: anyio.abc.TaskGroup | None = None
        self.sdk_initialize_request: dict | None = None
        self.captured_mcp_response: dict | None = None
        self.turn2_model_input: dict | None = None
        self.exit_after_result = False

    async def connect(self) -> None:
        self._ready = True

    def is_ready(self) -> bool:
        return self._ready

    async def write(self, data: str) -> None:
        for line in data.splitlines():
            if not line.strip():
                continue
            msg = json.loads(line)
            if msg.get("type") == "control_request" and msg["request"]["subtype"] == "initialize":
                self.sdk_initialize_request = msg["request"]
                await self._send.send({"type": "control_response", "response": {
                    "subtype": "success", "request_id": msg["request_id"],
                    "response": {"commands": [], "models": [], "account": {}}}})
            elif msg.get("type") == "control_response":
                rid = msg["response"]["request_id"]
                self._answers[rid] = msg["response"]
                self._pending[rid].set()
            elif msg.get("type") == "user":
                assert self._tg is not None
                self._tg.start_soon(self._run_turn)

    async def _ask_sdk(self, jsonrpc: dict) -> dict:
        """Send one mcp_message control request to the SDK and wait for its control_response."""
        self._n += 1
        rid = f"cli_req_{self._n}"
        self._pending[rid] = anyio.Event()
        await self._send.send({"type": "control_request", "request_id": rid, "request": {
            "subtype": "mcp_message", "server_name": SERVER_NAME, "message": jsonrpc}})
        await self._pending[rid].wait()
        return self._answers[rid]

    async def _run_turn(self) -> None:
        sid = "fake-session"
        if self.mode == "max_turns":
            # Shape copied from the CLI 2.1.310 source: subtype error_max_turns, is_error true,
            # errors [`Reached maximum number of turns (${maxTurns})`].
            await self._send.send({
                "type": "result", "subtype": "error_max_turns", "is_error": True,
                "duration_ms": 0, "duration_api_ms": 0, "num_turns": 4, "session_id": sid,
                "errors": ["Reached maximum number of turns (3)"],
                "terminal_reason": "max_turns"})
            self.exit_after_result = True
            await self._send.aclose()
            return

        # MCP handshake, as the CLI does for an "sdk" server
        await self._ask_sdk({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "protocolVersion": mcp.types.LATEST_PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "fake-claude-code", "version": "0"}}})
        await self._ask_sdk({"jsonrpc": "2.0", "method": "notifications/initialized"})
        await self._ask_sdk({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

        # Turn 1: the scripted model calls the tool
        tool_use_id = "toolu_fake_01"
        await self._send.send({"type": "assistant", "parent_tool_use_id": None, "session_id": sid,
                               "message": {"role": "assistant", "model": "fake-model",
                                           "content": [{"type": "tool_use", "id": tool_use_id,
                                                        "name": FULL_TOOL_NAME,
                                                        "input": TURN1_ARGS}]}})
        answer = await self._ask_sdk({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                      "params": {"name": "create_ticket",
                                                 "arguments": TURN1_ARGS}})
        self.captured_mcp_response = answer
        mcp_result = answer["response"]["mcp_response"]["result"]

        # Turn 2 input: the tool_result the CLI puts in the next API request (reconstructed)
        block = cli_tool_result_from_mcp(mcp_result, tool_use_id)
        self.turn2_model_input = {"role": "user", "content": [block]}
        await self._send.send({"type": "user", "parent_tool_use_id": None, "session_id": sid,
                               "message": {"role": "user", "content": [block]}})

        # Turn 2: the scripted model answers in text, and the run ends normally
        await self._send.send({"type": "assistant", "parent_tool_use_id": None, "session_id": sid,
                               "message": {"role": "assistant", "model": "fake-model",
                                           "content": [{"type": "text",
                                                        "text": "(scripted turn 2 reply)"}]}})
        await self._send.send({"type": "result", "subtype": "success", "is_error": False,
                               "duration_ms": 0, "duration_api_ms": 0, "num_turns": 2,
                               "session_id": sid, "result": "(scripted turn 2 reply)"})

    async def end_input(self) -> None:
        # The CLI exits once stdin closes after the run; end the stream the same way.
        with anyio.move_on_after(0.2):
            await anyio.sleep(0.05)
        await self._send.aclose()

    async def read_messages(self):  # type: ignore[override]
        async with anyio.create_task_group() as tg:
            self._tg = tg
            async with self._recv:
                async for msg in self._recv:
                    yield msg
            tg.cancel_scope.cancel()
        if self.exit_after_result:
            # what SubprocessCLITransport raises when the CLI exits with code 1
            raise ProcessError("Command failed with exit code 1", exit_code=1,
                               stderr="Check stderr output for details")

    async def close(self) -> None:
        self._ready = False


async def section_query_loop() -> None:
    hr("3. REAL query() LOOP, ALL DEFAULTS (only mcp_servers set), FAKE CLI ON THE TRANSPORT")
    server = create_sdk_mcp_server(SERVER_NAME, tools=[create_ticket])
    options = ClaudeAgentOptions(mcp_servers={SERVER_NAME: server})
    fake = FakeClaudeCode("tool_error")
    stream: list[str] = []
    raised: BaseException | None = None
    try:
        async for m in query(prompt="Open a high priority ticket: CSV export times out.",
                             options=options, transport=fake):
            if isinstance(m, AssistantMessage):
                for b in m.content:
                    if isinstance(b, ToolUseBlock):
                        stream.append(f"AssistantMessage ToolUseBlock name={b.name} "
                                      f"input={json.dumps(b.input)}")
                    elif isinstance(b, TextBlock):
                        stream.append(f"AssistantMessage TextBlock text={b.text!r}")
            elif isinstance(m, UserMessage) and isinstance(m.content, list):
                for b in m.content:
                    if isinstance(b, ToolResultBlock):
                        stream.append(f"UserMessage ToolResultBlock is_error={b.is_error} "
                                      f"content={b.content!r}")
            elif isinstance(m, ResultMessage):
                stream.append(f"ResultMessage subtype={m.subtype} is_error={m.is_error}")
    except BaseException as e:  # noqa: BLE001 - we want to report anything that escaped
        raised = e
    print("permission enforcement note: allowed_tools/permission_mode are enforced inside the "
          "CLI, which this\nscript does not run. With every option at its default, the real CLI "
          "(2.1.310) starts in\n'default' mode with no approver, so it would deny this MCP call "
          "before the handler runs.\nThis section shows what the model reads once the call is "
          "allowed to run.")
    show("\nSDK initialize control request (what the SDK told the CLI)", fake.sdk_initialize_request)
    print(f"\nexception escaped query(): {type(raised).__name__ + ': ' + str(raised) if raised else 'none'}")
    show("\nCAPTURED: SDK control_response to the CLI's tools/call (real SDK output, verbatim)",
         fake.captured_mcp_response)
    show("\nTURN 2 MODEL INPUT: tool_result the CLI sends to the model "
         "(reconstructed from CLI 2.1.310 source)", fake.turn2_model_input)
    print("\nmessages your app saw from query():")
    for s in stream:
        print(f"  {s}")


async def section_max_turns() -> None:
    hr("5. TURN LIMIT BOUNDARY: CLI ends the run with error_max_turns, then exits 1")
    print("default: ClaudeAgentOptions().max_turns = None -> no --max-turns flag -> no limit "
          "(docs: 'No limit').")
    print("knob: max_turns=N -> --max-turns N. Below, the fake CLI ends the run the way the CLI "
          "does at the limit.")
    fake = FakeClaudeCode("max_turns")
    got: list[str] = []
    try:
        async for m in query(prompt="loop forever", options=ClaudeAgentOptions(max_turns=3),
                             transport=fake):
            if isinstance(m, ResultMessage):
                got.append(f"ResultMessage subtype={m.subtype} is_error={m.is_error} "
                           f"result={m.result!r} errors={m.errors} "
                           f"terminal_reason={m.terminal_reason}")
        print("exception escaped query(): none")
    except ResultError as e:
        print("yielded before the raise:")
        for g in got:
            print(f"  {g}")
        print(f"exception escaped query(): {type(e).__name__} (subclass of ProcessError)")
        print(f"  str(e)          = {str(e)!r}")
        print(f"  e.subtype       = {e.subtype!r}")
        print(f"  e.errors        = {e.errors!r}")
        print(f"  e.exit_code     = {e.exit_code!r}")
        print(f"  e.terminal_reason = {getattr(e, 'terminal_reason', None)!r}")


async def main() -> None:
    section_defaults()
    await section_mcp_server()
    await section_query_loop()
    await section_max_turns()


if __name__ == "__main__":
    anyio.run(main)
