# Framework defaults: what the model reads after a failed call

The Part 1 experiment runs on the OpenAI Agents SDK, and your team may use another framework.
These checks put the same failing ticket tool into eight agent frameworks and leave every default
alone. The same rejected call then ends three ways. In some frameworks the run stops and the model
reads nothing. In others the model reads the raw exception, or a fixed line that hides it. Find
your framework below to see what your agent does today and which setting changes it.

![Eight frameworks in three groups. The run stops: LangGraph and LangChain (9,999 or 10,007 steps, then an exception), Google ADK (500 model calls, then an exception) and Pydantic AI (50 model requests, then an exception). The model reads the raw exception: Strands Agents (no limit), CrewAI (25 iterations, then a forced final answer) and the Claude Agent SDK (no limit). The model reads a fixed line: the OpenAI Agents SDK (10 turns, then an exception) and Microsoft Agent Framework (40 rounds, then a forced final answer). Each row names the setting that sets what the model reads and the setting that changes the loop limit.](../figures/framework-defaults.png)

*The ticket tool from Part 1 inside each framework's own agent loop, on its latest release, with
every default left alone. A scripted stand-in plays the model, so the figure shows only what each
framework sends.*

## What the checks do

Each folder holds one framework's check script, a `requirements.txt` that pins every package, and
the output the script printed. Each script builds an agent with the framework's own agent loop and
gives it a `create_ticket` tool. The tool calls the made-up ticket service from
`../experiment/servers.py`, copied into each script word for word. The service accepts only the
codes P0, P1 and P2. When the agent sends priority "high", the service rejects the call with an
HTTP 422 error that lists the three codes.

A scripted stand-in model plays the agent. On its first turn it calls the tool with "high". The
script then records what the framework hands the model on the second turn. No real model runs, so
the checks need no API key. Each script removes provider keys before it imports the framework, and
most of them also block every network connection. The ones that count connection attempts print 0.

The summaries below answer the same seven questions for each framework:

1. What does the model read after the tool raises the 422?
2. What does the model read when its arguments fail the tool's own schema, such as `priority=123`?
3. Which setting lets your team write that text itself?
4. Which loop limit ships on, and what happens when a run reaches it?
5. Is there a token or cost budget?
6. Must a person approve the tool call?
7. Does the framework retry a failed tool on its own?

Each script first runs with every default left alone. To show a setting, it then turns on that one
setting in a section of the output marked as not a default (NON-DEFAULT, KNOB or OPT-IN).

## The eight frameworks at a glance

| Framework | After the tool raises, the model reads | Set what the model reads with | Loop limit by default |
|---|---|---|---|
| LangGraph and LangChain | Nothing. The run stops and your code gets the exception. | `ToolErrorMiddleware` on `create_agent`, `handle_tool_errors` on `ToolNode` | 9,999 steps on `create_agent`, 10,007 on `ToolNode` graphs and `create_react_agent`, then an exception |
| Google ADK | Nothing. The run stops. | `on_tool_error_callback` | 500 model calls, then an exception |
| Pydantic AI | Nothing. The run stops. | raise `ToolFailed` or `ModelRetry` in the tool, or a capability for every tool | 50 model requests, then an exception |
| Strands Agents | The raw exception, with the whole 422 body | an `AfterToolCallEvent` hook | No limit. The run goes on until Python's recursion limit raises. |
| CrewAI | The raw exception, with the whole 422 body | an `after_tool_call` hook | 25 iterations, then a forced final answer. The 5th identical call raises. |
| Claude Agent SDK | The raw exception, once the tool call is approved | return `is_error` from the tool | No limit. The run goes on while the model calls tools. |
| OpenAI Agents SDK | A fixed line: "An error occurred while running the tool. Please try again." | `tool_error_formatter` for every tool, `failure_error_function` for one | 10 turns, then an exception |
| Microsoft Agent Framework | A fixed line: "Error: Function failed." | function middleware | 40 rounds, then a forced final answer. 3 failed rounds in a row force it sooner. |

None of the eight sets a token or cost budget by default. Only the Claude Agent SDK requires
approval for a custom tool by default, and even there a settings file can turn that off. On the
normal tool-calling path, none of the eight runs a failed tool again on its own. CrewAI's ReAct
text path is the one exception.

## Per framework

Each summary below lists what the check found. Some facts, such as when a setting first shipped,
come from the framework's source code at the release tag rather than from the script's output.

### LangGraph and LangChain

langchain 1.4.7, langchain-core 1.7.0, langgraph 1.2.18 and langgraph-prebuilt 1.1.1. The checks
cover `langchain.agents.create_agent`, the current entry point, `langgraph.prebuilt.create_react_agent`,
deprecated since LangGraph v1 but still shipped, and a graph built by hand with `ToolNode`.

- **After the tool raises.** The run stops. The 422 exception reaches the code that called
  `agent.invoke()`, the tool runs once, and the model is never called again, so it reads nothing.
  `create_agent` and `create_react_agent` behave the same way, because both build a `ToolNode` with
  the default handler. That handler raises every error again except `ToolInvocationError`. A graph
  built by hand with `ToolNode(tools)` stops the same way (`output-toolnode-graph.txt`).
- **Bad arguments.** When the arguments fail the tool's own schema, the run goes on and the tool
  function never runs. The model gets a tool message with status "error" that repeats the
  arguments and the field error, then "Please fix the error and try again." This holds for both
  `create_agent` and `create_react_agent`.
- **Set what the model reads.** On `create_agent`, add `ToolErrorMiddleware(on_error=fn)`, new in
  langchain 1.3.14 (2026-07-16). `fn(exc, request)` returns the text, or `None` to let the
  exception through, and `tools=[...]` limits it to the tools you name. On a bare `ToolNode`, which
  you can also pass to `create_react_agent`, set `ToolNode(handle_tool_errors=...)`. It takes a
  string, a function, an exception type or tuple, or `True`. Both send your text to the model as a
  tool message with status "error".
- **Loop limit.** The limit is LangGraph's `recursion_limit`, counted in graph steps. With no
  middleware, each model call and each tools run is one step, and every middleware hook node
  (`before_model`, `after_model` and so on) adds one more step per turn. `create_agent` sets 9_999.
  Plain graphs and `create_react_agent` use the langgraph 1.2.18 default of 10_007, which the
  `LANGGRAPH_DEFAULT_RECURSION_LIMIT` environment variable replaces. `create_agent` ignores that
  variable. At these defaults with no middleware, both raise `GraphRecursionError` to the caller,
  `create_agent` after 5,000 model calls and `create_react_agent` after 5,004.
  `create_react_agent` writes the reply "Sorry, need more steps to process this request." but the
  reply survives only at even limits. At odd limits, 10_007 included, the agent writes that reply
  and LangGraph raises anyway. On `create_agent`, `ModelCallLimitMiddleware(run_limit=N)`, with its
  default `exit_behavior='end'`, ends the run with the message "Model call limits exceeded: run
  limit (N/N)" instead. These defaults have moved over time. The langgraph default was 25 through
  1.0.5, 10_000 from 1.0.6 to 1.1.3, and 10_007 since 1.1.4 (2026-03-31). `create_agent` set no
  limit of its own in langchain 1.0.0 to 1.0.4, set 10_000 from 1.0.5 (2025-11-07) through 1.2.13,
  and has set 9_999 since 1.2.14 (2026-03-31).
- **Budget.** Neither library has a built-in token or cost budget, and `create_agent` installs no
  middleware by default. Caps on call counts exist only as middleware you add,
  `ModelCallLimitMiddleware(thread_limit=None, run_limit=None)` and
  `ToolCallLimitMiddleware(thread_limit=None, run_limit=None, exit_behavior='continue')`. The only
  cap on by default is the `recursion_limit` step count.
- **Approval.** Built in, but off by default. On `create_agent` it is
  `HumanInTheLoopMiddleware(interrupt_on={tool_name: True | InterruptOnConfig})`, which needs a
  checkpointer and resumes with `Command(resume=...)`. Tools not listed in `interrupt_on` are
  approved automatically. A lower-level option is `interrupt_before=['tools']` on `create_agent` or
  `create_react_agent`.
- **Retry.** With defaults, neither entry point retries a failed tool or prompts the model again.
  The tool ran once, the model was called once, and the graph nodes carry no `RetryPolicy`. Retry
  is opt-in through `ToolRetryMiddleware`. Its default `max_retries=2` means 3 attempts, and its
  default `on_failure='continue'` sends an error tool message to the model after the last failure.

### Strands Agents

strands-agents 1.62.0, the Python SDK.

- **After the tool raises.** The run goes on. The `@tool` decorator catches the exception, and on
  turn 2 the model gets a user-role `toolResult` with status "error" and the text "Error:
  <exception class name> - <str(exception)>". The whole 422 body, allowed values included, reaches
  the model.
- **Bad arguments.** Arguments that fail the tool's own schema never reach the function. The model
  gets an error `toolResult` that reads "Error: Validation failed for input parameters: " plus
  pydantic's full message, and the run goes on. Arguments that are not valid JSON are quietly
  replaced with `{}`, with only a logged warning, and the agent's own `toolUse` in the history is
  stored with input `{}` too. The model is never told its JSON was broken. For required arguments
  it reads "Field required" errors. If all of a tool's arguments have defaults, the tool silently
  runs with those defaults and returns success.
- **Set what the model reads.** There is no error-text option. A team can replace the text in two
  ways. One is an `AfterToolCallEvent` hook that sets `event.result` and can read
  `event.exception`. The other is middleware made public in 1.62.0,
  `agent.add_middleware(ExecuteToolStage.Output, fn)`, which returns a new `ToolResultEvent`. Both
  apply to every tool on that agent, so to change one tool, filter on the tool name. A single tool
  can also catch its own exception and return a `{"status": "error", "content": [...]}` dict,
  which the decorator passes through unchanged.
- **Loop limit.** A single `Agent` has no default turn limit. Each turn calls the next one
  recursively, so unless something cancels the run, a model that keeps calling tools runs until
  Python's recursion limit raises `EventLoopException` (cause `RecursionError`) to the caller. The number of model calls before that is a side effect,
  not a setting. It was 319 in the check (CPython 3.12.13, recursion limit 1000). Every recovery
  from a context-window overflow resets the stack depth, and a probe with one overflow reached 569
  calls. The setting is per call, `agent(prompt, limits={"turns": N})`, available since 1.42.0. It
  stops with `stop_reason` "limit_turns" and raises nothing. Tools that the Nth turn asked for
  still run first. It returns no final answer: `str(result)` is empty and `result.message` is the
  last tool result.
- **Budget.** The only run-level budget is the per-call `limits` argument: `turns` (in effect a
  count of model calls, not counting throttle retries), `total_tokens` and `output_tokens`. All
  default to `None`, so there is no budget unless the caller passes one. The token caps are soft
  and checked at turn boundaries, so a run can overshoot by one turn. They stop with `stop_reason`
  "limit_total_tokens" or "limit_output_tokens". There is no money budget. A provider's
  `max_tokens` setting caps only the output of one model call.
- **Approval.** A built-in approval step ships, the `HumanInTheLoop` intervention (since 1.44.0),
  and it is off by default (`interventions=None` on `Agent`). With
  `interventions=[HumanInTheLoop()]`, every tool needs approval. Without an `ask` callback the run
  pauses before the tool with `stop_reason` "interrupt". With `ask=`, a denial reaches the model as
  an error `toolResult`. Lower-level hooks are `BeforeToolCallEvent.interrupt()` and `cancel_tool`.
- **Retry.** The framework never retries a failed tool on its own. The raising tool ran exactly
  once, and the error became the next turn of the normal loop. A tool runs again only if the team
  opts in, with a hook that sets `AfterToolCallEvent.retry = True` or with `ExecuteToolStage` Wrap
  middleware that calls `next_fn` again. Separately, the default `ModelRetryStrategy` retries the
  model call, not the tool, and only on `ModelThrottledException`. It makes 6 attempts in all, with
  delays that start at 4 seconds and are capped at 240. `retry_strategy=None` turns it off.

### Google Agent Development Kit (ADK)

google-adk 2.13.0.

- **After the tool raises.** The run stops. The model never gets a tool result. The original
  `ServerValidationError`, with its full 422 text, reaches the caller of `runner.run_async()`
  after one model turn.
- **Bad arguments.** A missing required argument goes back to the model instead of raising. The
  function does not run, and the model reads an `{"error": ...}` dict as a `function_response`
  part (content role "user"), with no flag beyond the `error` key. A wrong-typed argument
  (`priority=123`) is not checked by default, so the function runs and the server exception stops
  the run, as above.
- **Set what the model reads.** Use `on_tool_error_callback`. It can go on one agent,
  `LlmAgent(on_tool_error_callback=...)`, a field added in v1.18.0, or on a runner-wide
  `BasePlugin.on_tool_error_callback`, added in v1.9.0. Plugins run first. A returned dict becomes
  the tool result the model reads. Returning `None` raises the exception again.
- **Loop limit.** `RunConfig.max_llm_calls` defaults to 500. The `ADK_MAX_LLM_CALLS` environment
  variable overrides it, and a value of 0 or less removes the limit. On the 501st model call ADK
  raises `LlmCallsLimitExceededError` to the caller. No setting turns the limit into a final
  answer.
- **Budget.** There is no token or cost budget in `RunConfig` or the runner. The only built-in cap
  is the count of model calls, `max_llm_calls` = 500.
- **Approval.** A human approval step exists but is off by default,
  `FunctionTool(func, require_confirmation=False)`, which also takes a bool or a function (added in
  v1.14.0). When it is on, the tool does not run. The run pauses with an
  `adk_request_confirmation` function call and does not call the model again.
- **Retry.** By default ADK does not retry a failed tool or prompt the model again. The tool body
  ran once and the run stopped. Two retry paths are opt-in. The first is the built-in
  `ReflectAndRetryToolPlugin` (since v1.16.0, default `max_retries=3`), which returns the error
  plus reflection guidance as the tool result. In the check it gave 3 guidance results, then a
  `RuntimeError` on the 4th failure. The second is `retry_config`, which `LlmAgent` inherits from
  `BaseNode` (default `None`). With a `RetryConfig` set, ADK runs the whole agent again after the
  tool raises, and the model's retry request held only the user message, not the failed call or
  the error. So the model is asked again without seeing why the first try failed.

### CrewAI

crewai 1.15.30.

- **After the tool raises.** The run goes on. On the native tool-calling path, the model gets an
  ordinary tool message whose content is "Error executing tool: " plus `str(exception)`. The full
  422 body reaches the model with no error flag, and the Anthropic provider adds none when it
  converts the message. `Crew.kickoff()` and `Agent.kickoff()` behave the same way. The provider
  class picks the path from the model name, not from whether the model can call tools:
  - OpenAI: native unless the name contains "o1".
  - Azure: native only if the name contains "gpt-", "o1-" or "text-". So o3, o4-mini, Mistral,
    Llama or a custom deployment name fall back to ReAct.
  - Gemini: native only for names like gemini-N with N of 1.5 or more.
  - Anthropic and Bedrock: native by default.
  - A bare custom `BaseLLM`: never native.

  The executor also switches to ReAct in the middle of a run if the provider says tools are
  unsupported. On the ReAct path the model reads "I encountered an error while trying to use the
  tool. This was the error: <same text>. Tool create_ticket accepts these inputs: ...", then
  "Moving on then.", the format reminder, and a user turn that says "Analyze the tool result...".
- **Bad arguments.** Arguments that fail the tool's own schema never reach the tool body. They come
  back through the same tool-result channel, with the pydantic error and a schema hint (the
  expected arguments and the required fields). JSON that does not parse gets a separate message.
- **Set what the model reads.** Use an `after_tool_call` hook. Any string it returns replaces what
  the model reads, on both paths. Register it with `@after_tool_call` or
  `register_after_tool_call_hook`. It is global, and the decorator can narrow it with `tools=[...]`
  or `agents=[...]`. For one tool, the tool can catch its own error and return
  `ToolFailure(message, code)`. The model then reads "<message> (code: <code>)".
- **Loop limit.** `Agent.max_iter` defaults to 25. At the limit nothing is raised. The loop makes
  one more model call with no tools and a user message that demands a final answer, and that reply
  becomes the run's normal output. No extra setting is needed to get a final answer instead of an
  exception. Separately, and new in 1.15.29, the 5th identical call (same tool, arguments and
  result) raises `ToolExecutionFailedError` to the caller.
- **Budget.** No cost, token or spend budget is on by default. `max_rpm` is `None` on both the
  agent and the crew. When set, it counts requests per minute, and once the count is hit it sleeps
  a flat 60 seconds and then carries on, so it slows the run and never stops it.
  `max_execution_time` is `None`. `Agent.max_tokens` is `None` and is never passed to the model.
  The only defaults that stop a runaway tool loop are `max_iter=25` and the stop on the 5th
  identical call. Two other defaults change spend without capping it. `max_retry_limit=2` runs a
  task that raised again, up to 3 attempts. `respect_context_window=True` summarises a history that
  overflows the context window with extra model calls.
- **Approval.** There is no built-in approval step per tool, so nothing is on by default.
  `Task.human_input` (default `False`) asks a person to review the agent's final answer, not its
  tool calls. A team builds an approval gate as a `before_tool_call` hook that returns `False`, and
  `ToolCallHookContext.request_human_input` helps with that console prompt. When a hook blocks the
  call, the model reads "Tool execution blocked by hook. Tool: create_ticket".
- **Retry.** It depends on the path. On the native tool-calling path, CrewAI does not retry the
  tool or add a prompt. The tool runs once and the error goes back to the model. On the ReAct text
  path, `ToolUsage` runs a failing call again before the model sees anything, up to 3 attempts (2
  if a `function_calling_llm` in `OPENAI_BIGGER_MODELS` is set). When the call has arguments, each
  attempt calls the tool twice, first with the arguments the schema filtered and then with the raw
  ones. So a raising tool body ran 6 times. A call with no arguments runs once per attempt. The
  model never sees the earlier attempts, though each one emits a `ToolUsageErrorEvent`. Two other
  layers retry too. `Agent.max_retry_limit=2` runs the whole task again when the executor raises,
  except for `ToolExecutionFailedError`, `HookAborted` and litellm exceptions. `BaseLLM`
  subclasses retry rate-limit errors up to 3 attempts. Neither layer runs a tool again on its own.

### Pydantic AI

pydantic-ai-slim 2.61.0.

- **After the tool raises.** A tool that raises an ordinary exception, anything other than
  `ModelRetry` or `ToolFailed`, ends the run. The model is called once and never gets a tool
  result, and `run_sync` raises the original `ServerValidationError` again, unwrapped, with its full
  422 text. The default `on_tool_execute_error` hook just raises again, and only
  `ToolRetryError`, `ToolFailedError` and `RunCancelled` become results.
- **Bad arguments.** Arguments that fail the tool's own schema do not end the run. The model gets a
  `ToolReturnPart` with `outcome='retried'` whose content is the pydantic error list, with `input`
  kept and `ctx` dropped, flagged as an error. OpenAI Chat (`role=tool`) and OpenAI Responses
  (`function_call_output`) both send `{"error":[...]}`. Anthropic sends the bare JSON list as one
  text block with `is_error=true`. The suffix "Fix the errors and try again." has been gone only
  since 2.60.0 (2026-10-23), the release before the one checked. In 2.0.0 to 2.59.0, and in the
  1.x line through 1.107.9, the model got the `RetryPromptPart` text instead: "N validation
  error(s):", a fenced JSON block, then "Fix the errors and try again." `ModelRetry` text got the
  same suffix then too. In 2.61.0 the suffix lives on only in `RetryPromptPart.model_response()`,
  and it reaches the model only for a legacy `RetryPromptPart` with no tool name.
- **Set what the model reads.** No option sets the error text, so the team writes the conversion.
  For one tool, catch the exception and raise `ModelRetry(text)`, which gives outcome 'retried'
  and uses the tool's retry budget, or `ToolFailed(text)`, which gives outcome 'failed' and uses no
  budget. `ToolFailed` first appears in 2.16.0 (2026-07-23). For every tool at once, pass
  `Agent(capabilities=[...])` with a capability that overrides `on_tool_execute_error`, present
  since 1.71.0 (2026-03-24). The hook can return a value to use as the result, or raise
  `ToolFailed` or `ModelRetry` so the model gets the text flagged as an error. When the 422 comes
  back on every call, `ModelRetry` ends the run at the second failure, and `ToolFailed` lets the
  run go on to the loop limit (`output-repeat-failure.txt`).
- **Loop limit.** The loop limit is `UsageLimits.request_limit=50` agent-loop turns, applied by
  default when `usage_limits` is not passed. At the limit the run raises `UsageLimitExceeded`
  before the 51st request and returns no partial answer. No built-in setting turns the limit into
  a final answer, and `end_strategy` only covers tool calls that arrive alongside a final result.
  The docs show catching `UsageLimitExceeded` and point to `ctx.usage_limits`, so a team's own
  tools or capabilities can read the budget and wind down. The team writes that code, because the
  framework has no fallback.
- **Budget.** `UsageLimits` is a budget object, with `cost_limit` (USD), `tool_calls_limit`,
  input, output and total token limits, and `per_request_input_tokens_limit`. All of them default
  to `None`, so nothing caps cost, tokens or tool calls by default. The only default cap is
  `request_limit=50`.
- **Approval.** A built-in approval step exists, and it is off by default (`requires_approval=False`
  on `Tool` and on `@agent.tool` and `@agent.tool_plain`). Turned on, the tool body does not run.
  With the default `output_type=str` the run raises `UserError`. With `DeferredToolRequests` in
  `output_type`, the run returns the pending call in `DeferredToolRequests.approvals` for a person
  to approve and resume with `DeferredToolResults`. A tool can also ask for approval only in some
  cases by raising `ApprovalRequired`.
- **Retry.** The framework never runs a tool again after it raised an ordinary exception. The run
  just stops. For a schema failure or a `ModelRetry`, it prompts the model again with the retried
  result. The default budget is 1 retry per tool (`Agent` retries default 1,
  `ToolManager.default_max_retries=1`). The next failure of the same tool raises
  `UnexpectedModelBehavior`. The count resets for a tool once it succeeds.

### Microsoft Agent Framework

agent-framework-core 1.23.0, the Python package.

- **After the tool raises.** The run goes on. On turn 2 the model gets a role "tool" message with
  one `function_result` whose only text is "Error: Function failed." The exception text, the full
  422 body, stays in a host-side `exception` field and does not reach the result text.
- **Bad arguments.** The framework checks arguments against the tool's own pydantic schema before
  the body runs. A wrong type (`priority=123`), a missing argument or broken JSON gives the model
  "Error: Argument parsing failed.", a different text from the one above. The pydantic detail goes
  only in the host-side `exception` field.
- **Set what the model reads.** There are two ways. Globally, set `include_detailed_errors=True` in
  the client's `function_invocation_configuration`, which appends " Exception: <str(exc)>". It has
  been off by default since python-1.0.0. Per agent or per run, write a function middleware
  (`@function_middleware` or a `FunctionMiddleware` subclass, passed as `Agent(middleware=[...])`)
  that wraps `call_next()` in try/except and sets `context.result` to the team's text. No per-tool
  option for the error text exists.
- **Loop limit.** The default limit is `max_iterations=40` model round trips. At the limit nothing
  is raised. The loop makes one more model call with `tool_choice="none"` and returns that reply as
  the final answer. If that reply has no text, the framework writes in a fixed line, "Function
  invocation limit reached before a final answer could be produced." A final answer instead of an
  exception is already the default, so no setting is needed for it, and no option raises instead.
- **Budget.** The tool loop has no token or cost budget. It does have two optional limits,
  `max_function_calls` (total tool runs per request) and `max_duration_seconds` (wall-clock time),
  and both default to `None`, which means no limit. When either one is hit, tools are turned off
  and the model is made to write a text answer.
- **Approval.** A built-in human approval step per tool comes through
  `@tool(approval_mode="always_require")`, and it is off by default ("never_require"). When it is
  on, the run returns a `function_approval_request` in `response.user_input_requests` before the
  tool body runs, and the caller resumes the run with an approval response.
- **Retry.** The framework never runs a failed tool again on its own and never adds a retry prompt.
  It sends the error result back and the model decides what to do next. It does count rounds that
  end in an error. After 3 such rounds in a row (`max_consecutive_errors_per_request=3`) it turns
  tools off and makes one last model call for a text answer.

### Claude Agent SDK

claude-agent-sdk 0.2.174, the Python SDK, which bundles Claude Code CLI 2.1.310. The agent loop
runs inside that CLI, a closed-source binary. The check does not start it. It runs the SDK's own
side of the loop and stands in for the CLI, so the text the CLI sends the model on turn 2 is
rebuilt from the CLI's behaviour, as the output says. The research behind the check also captured
that text in a live run.

- **After the tool raises.** Once the call is allowed (see Approval below), a `@tool` handler that
  raises does not stop the run. The in-process MCP server returns `isError: true` with
  `str(exception)` as the only text. The CLI sends that text to the model as a `tool_result` with
  `is_error: true`, and the loop goes on. The CLI trims the text. Anything over about 11,000
  characters is cut to its first and last 5,000, around a "[N characters truncated]" marker.
  Unlike OpenAI 0.22.3, no fixed line comes before the exception text.
- **Bad arguments.** Arguments that fail the tool's own schema never reach the handler. The SDK
  checks them with jsonschema and returns `isError: true` with "Input validation error: " plus the
  jsonschema message. The CLI's MCP wrapper uses a passthrough input schema and does not check MCP
  arguments itself, so this is the text the model reads, as a `tool_result` with `is_error` true.
- **Set what the model reads.** Neither `@tool` nor `create_sdk_mcp_server` has an option for the
  error text. To change what the model reads, return `{"content": [...], "is_error": True}`
  yourself. You can do it in each handler, in one wrapper applied to every handler, or in a
  hand-built `mcp.server.Server` passed as the SDK server instance. On this path `PostToolUse` does
  not fire. `PostToolUseFailure` fires, but it can only add `additionalContext`, which the model
  reads as a separate message after the unchanged error. `updatedToolOutput` and
  `updatedMCPToolOutput` are ignored there.
- **Loop limit.** `max_turns` defaults to `None`, and 0 counts as unset too, so the SDK passes no
  `--max-turns`. The CLI then reads `CLAUDE_CODE_MAX_TURNS` from the environment, which the SDK
  passes through. Only when that is unset too does the loop run until the model stops calling
  tools. At the limit the CLI ends with a `ResultMessage` of subtype "error_max_turns" (`is_error`
  True, `result` None). `query()` yields it and then raises `ResultError`. `ClaudeSDKClient` gets
  the same result without raising and keeps the session open. No option turns the limit into a
  final answer. The limit counts tool-use turns, and loading a deferred MCP tool through ToolSearch
  (on by default) spends one.
- **Budget.** There is a dollar budget, `max_budget_usd`, and it is off by default (`None`, with no
  `--max-budget-usd` flag). When set, the CLI ends the run with a `ResultMessage` of subtype
  "error_max_budget_usd". It checks spend after each model response, so a run can overshoot by one
  response. A token `task_budget` also exists, as an API beta, and is off by default. There is no
  request-count budget.
- **Approval.** For custom tools, approval is required by default, with one condition. In a run
  with no settings files and with `permission_mode`, `can_use_tool` and `allowed_tools` unset, CLI
  2.1.310 (2.1.302 and later) starts in "default" mode and denies the MCP call before the handler
  runs. The model reads "Claude requested permissions to use mcp__tickets__create_ticket, but you
  haven't granted it yet." and the call is listed in `ResultMessage.permission_denials`. But
  `setting_sources` defaults to loading user, project and local settings. An allow rule, or a
  `permissions.defaultMode` such as `bypassPermissions`, in any of those files approves the call
  with no SDK option set. Pass `setting_sources=[]` to make this independent of the machine. A
  `can_use_tool` callback adds `--permission-prompt-tool stdio`.
  `allowed_tools=['mcp__tickets__create_ticket']` approves the tool with no prompt.
- **Retry.** None. The SDK calls the handler once per `tools/call` and has no retry loop. The CLI
  sends the error to the model, and the model decides whether to call again. The CLI does retry
  failed model API requests (`CLAUDE_CODE_MAX_RETRIES`, default 10), which is separate from tool
  calls.

### OpenAI Agents SDK

openai-agents 0.24.0, the version the Part 1 experiment runs on. Its facts come from this folder's
`output.txt` and match `../experiment/sdk_defaults.txt` on every point the two share.

- **After the tool raises.** The run goes on. The tool body ran once, and on turn 2 the model gets
  a `function_call_output` item whose output is the fixed line "An error occurred while running the
  tool. Please try again." with no error flag. Nothing from the 422 body reaches the model, not the
  field, not the value it sent and not the allowed codes. Up to 0.22.3 the default added "Error:"
  and the raw exception after that line.
- **Bad arguments.** When the arguments fail the tool's own schema (`priority=123` or `priority`
  missing), or the JSON does not parse, the tool body never runs and the model reads the same
  fixed line. It is not told which argument was wrong. A call to a tool name that does not exist
  stops the run with `ModelBehaviorError` after one model call, because
  `RunConfig.tool_not_found_behavior` defaults to "raise_error".
- **Set what the model reads.** For one tool, pass `function_tool(f, failure_error_function=fn)`.
  For every tool in a run, set `RunConfig(tool_error_formatter=fn)`, new in 0.24.0. A per-tool
  `failure_error_function` wins. With both set, the model read the per-tool text and the formatter
  was called 0 times. On a schema failure the formatter is called too, but the exception it gets
  reads only "Invalid JSON input for tool create_ticket", so it cannot tell which field failed.
  `failure_error_function=None` stops the run instead, with a `UserError` whose cause is the 422.
- **Loop limit.** `DEFAULT_MAX_TURNS` is 10, and `Runner.run` uses it when `max_turns` is not
  passed. A model that calls a tool forever made 10 model calls and 10 tool runs, then the run
  raised `MaxTurnsExceeded` to the caller. With `error_handlers={"max_turns": handler}`, the run
  returns the handler's `final_output` instead, after the same 10 calls.
- **Budget.** None. `RunConfig` has no field, and `Runner.run` no parameter, named for a budget,
  cost, token, usage, request or retry limit. In the turn-limit run the stand-in reported 1,000,000
  input tokens per call, 10,000,000 in all, and only the turn limit stopped the run.
  `ModelSettings.max_tokens` is `None` by default, and when set it caps the output of one model
  call, not the run.
- **Approval.** `needs_approval=False` by default. With `function_tool(f, needs_approval=True)`
  the run returns with one pending `ToolApprovalItem`, and the tool does not run. After
  `state.reject(item)` and a second `Runner.run`, the model reads "Tool execution was not
  approved."
- **Retry.** No automatic tool retry. The tool body ran once, and the SDK called the model again
  with the fixed line. `ModelSettings.retry` is `None` by default, so retrying the model call is
  opt-in too.

## Run one check

You need Python 3.12 and [uv](https://docs.astral.sh/uv/). Each framework gets its own venv inside
its folder, and git ignores it. The LangGraph check, for example:

```bash
cd part1-loop-and-readback/framework-defaults/langgraph
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
.venv/bin/python -I check_langgraph_defaults.py > output.txt
git diff output.txt
```

Without uv, create the venv with `python3.12 -m venv .venv`, then install with
`.venv/bin/pip install -r requirements.txt`. Each `requirements.txt` pins the framework at the
version checked, and every other package at the version installed with it. The `-I` flag keeps
Python from loading anything outside the venv.

Each folder's command, run from that folder with its venv:

| Folder | Command |
|---|---|
| `langgraph` | `.venv/bin/python -I check_langgraph_defaults.py > output.txt` |
| | `.venv/bin/python -I check_langgraph_defaults.py --full-default-loop > output-full-default-loop.txt` |
| | `.venv/bin/python -I check_langgraph_toolnode_graph.py > output-toolnode-graph.txt` |
| `strands` | `.venv/bin/python -I -u check_strands_defaults.py > output.txt 2>&1` |
| `google-adk` | `.venv/bin/python -I check_adk_defaults.py > output.txt` |
| `crewai` | `.venv/bin/python -I -u check_crewai_defaults.py < /dev/null > output.txt 2>&1` |
| `pydantic-ai` | `.venv/bin/python -I check_pydantic_ai_defaults.py > output.txt` |
| | `.venv/bin/python -I check_repeat_failure.py > output-repeat-failure.txt` |
| `ms-agent-framework` | `.venv/bin/python -I check_maf_defaults.py > output.txt` |
| `claude-agent-sdk` | `.venv/bin/python -I check_claude_agent_sdk_defaults.py > output.txt` |
| `openai-agents` | `.venv/bin/python -I -u check_openai_agents_defaults.py > output.txt` |

The LangGraph default-loop runs play thousands of model turns, because the default limits are
9,999 and 10,007 steps, so they take a while. Google ADK logs the tracebacks of the failed runs to
stderr, which `output.txt` leaves out. The Strands check waits out the default 4 second retry delay
once.

A fresh venv built from each `requirements.txt`, with the network blocked, reproduced every output
here except three ids that change on every run: the `tracking_id` in the Strands output, the
confirmation call id in the Google ADK output and the `tool_call_id` in the Pydantic AI output.

## Dates and versions

Every version below was the latest stable release on PyPI on 2026-10-27, when the checks ran on
Python 3.12.

| Framework | Package | Version | Released on PyPI |
|---|---|---|---|
| LangGraph and LangChain | langchain | 1.4.7 | 2026-10-21 |
| | langchain-core | 1.7.0 | 2026-10-22 |
| | langgraph | 1.2.18 | 2026-10-26 |
| | langgraph-prebuilt | 1.1.1 | 2026-10-15 |
| Strands Agents | strands-agents | 1.62.0 | 2026-10-21 |
| Google ADK | google-adk | 2.13.0 | 2026-10-23 |
| CrewAI | crewai | 1.15.30 | 2026-10-24 |
| Pydantic AI | pydantic-ai-slim | 2.61.0 | 2026-10-24 |
| Microsoft Agent Framework | agent-framework-core | 1.23.0 | 2026-10-22 |
| Claude Agent SDK | claude-agent-sdk (bundles Claude Code CLI 2.1.310) | 0.2.174 | 2026-10-24 |
| OpenAI Agents SDK | openai-agents | 0.24.0 | 2026-10-15 |

A newer release can change any of these defaults. Run the check again after an upgrade and diff
the output.

## What the checks do not show

- What a real model does after it reads the text. The stand-in answers from a script, so the
  outputs show only what each framework sends. The Part 1 experiment measures real models, on the
  OpenAI Agents SDK only.
- Every way to run an agent. Each script drives the run call named in its output. Streaming runs,
  handoffs, sub-agents and hosted tools can behave differently.
- The Claude Code CLI itself. The Claude Agent SDK check stands in for the CLI, as described in its
  section.

## Layout

```
framework-defaults/
  README.md                this page
  <framework>/
    check_*.py             the check script, run from its folder
    requirements.txt       the framework and every package installed with it, pinned
    output*.txt            what the script printed
```
