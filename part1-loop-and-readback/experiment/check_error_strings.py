"""
Print what the installed SDK's default_tool_error_function returns for the errors this
experiment produces, as JSON. No model is called. Run it under each venv, from the part folder:

  .venv/bin/python experiment/check_error_strings.py          # current SDK (0.24.0)
  .venv-0.22.3/bin/python experiment/check_error_strings.py   # the last release before the change

The expected output of each is in expected/. harness_defaults.py runs the 0.22.3 one and checks
that its "old_default" arm returns, character for character, what the real 0.22.3 SDK returns
for the same errors.
"""

from __future__ import annotations

import importlib.metadata
import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from servers import ServerValidationError, sms_server, ticket_server  # noqa: E402


def make_errors() -> dict[str, Exception]:
    """The same exceptions in any SDK version: both server errors, a bad-JSON call, a crash."""
    from agents.exceptions import ModelBehaviorError
    from agents.tool import _parse_function_tool_json_input

    errs: dict[str, Exception] = {}
    for name, fn, kwargs in [
        ("priority_422", ticket_server, {"title": "CSV export times out", "priority": "high"}),
        ("phone_422", sms_server, {"to": "(415) 555-0132", "message": "Checkout is down"}),
    ]:
        try:
            fn(**kwargs)
        except ServerValidationError as exc:
            errs[name] = exc
    # how the SDK itself raises on unparsable arguments, with its default logging settings
    try:
        _parse_function_tool_json_input(tool_name="send_sms", input_json='{"to": "+1415')
    except ModelBehaviorError as exc:
        errs["bad_json_sdk"] = exc
    # the same with the JSONDecodeError attached (what the SDK raises when tool-data logging
    # is turned on), so the old function's JSON branch is exercised too
    try:
        try:
            json.loads('{"to": "+1415')
        except json.JSONDecodeError as jde:
            raise ModelBehaviorError('Invalid JSON input for tool send_sms: {"to": "+1415') \
                from jde
    except ModelBehaviorError as exc:
        errs["bad_json_with_cause"] = exc
    errs["crash"] = RuntimeError("connection reset by peer")
    return errs


def main() -> None:
    import agents
    from agents.tool import default_tool_error_function

    site = Path(agents.__file__).resolve().parent.parent
    src = Path(inspect.getsourcefile(default_tool_error_function)).resolve()
    print(json.dumps({
        "version": importlib.metadata.version("openai-agents"),
        "file": src.relative_to(site).as_posix(),   # relative, so the output is the same anywhere
        "line": inspect.getsourcelines(default_tool_error_function)[1],
        "source": inspect.getsource(default_tool_error_function),
        "outputs": {k: default_tool_error_function(None, e) for k, e in make_errors().items()},
    }))


if __name__ == "__main__":
    main()
