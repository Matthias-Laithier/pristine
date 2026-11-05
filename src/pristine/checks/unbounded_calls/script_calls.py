from collections.abc import Iterator
from pathlib import PurePath

from tree_sitter import Node

from pristine.calls import BoundedCall, calls_of, has_unknown_argument
from pristine.checks.unbounded_calls.calls import Violation
from pristine.findings import Severity
from pristine.parsing import ParsedFile, node_text

AXIOS = "axios"
AXIOS_FIX = "set timeout in the config, or call an axios.create({ timeout }) instance"
AXIOS_DEFAULT_TIMEOUT = "axios.defaults.timeout"
AXIOS_CONFIG_POSITIONS = {"get": 1, "delete": 1, "head": 1, "options": 1, "post": 2, "put": 2, "patch": 2, "request": 0}
FRONTEND_SEGMENTS = frozenset({"frontend", "web", "client", "components", "pages", "hooks"})
FRONTEND_SUFFIXES = frozenset({".tsx", ".jsx"})
APP_ROUTER_DIRECTORY = "src/app/"
QUOTES = "'\"`"
SPREAD = "..."
BROWSER_ONLY_KEYS = frozenset({"credentials", "keepalive", "mode"})
SCRIPT_CALLS = {
    "fetch": BoundedCall("signal", 1, Severity.WARNING, "pass signal: AbortSignal.timeout(<ms>) in the options"),
    **{
        f"{AXIOS}.{method}": BoundedCall("timeout", position, Severity.WARNING, AXIOS_FIX)
        for method, position in AXIOS_CONFIG_POSITIONS.items()
    },
}


def is_frontend(path: str) -> bool:
    file_path = PurePath(path)
    in_app_router = APP_ROUTER_DIRECTORY in file_path.as_posix()
    return in_app_router or file_path.suffix in FRONTEND_SUFFIXES or bool(FRONTEND_SEGMENTS & set(file_path.parts))


def script_call(callee: str, arguments: list[Node]) -> BoundedCall | None:
    if callee == AXIOS:
        return BoundedCall("timeout", int(arguments[0].type != "object"), Severity.WARNING, AXIOS_FIX)
    return SCRIPT_CALLS.get(callee)


def object_keys(config: Node) -> set[str]:
    return {
        (node_text(child.child_by_field_name("key") or child) or "").strip(QUOTES) for child in config.named_children
    }


def lacks_bound(arguments: list[Node], call: BoundedCall) -> bool:
    position = call.position or 0
    config = arguments[position] if len(arguments) > position else None
    if config is None or config.type != "object":
        return config is None
    keys = object_keys(config)
    is_browser_request = bool(BROWSER_ONLY_KEYS & keys)
    return call.bound not in keys and not is_browser_request and not any(key.startswith(SPREAD) for key in keys)


def is_unknown_or_relative(arguments: list[Node]) -> bool:
    if not arguments or has_unknown_argument(arguments):
        return True
    return (node_text(arguments[0]) or "").lstrip(QUOTES).startswith("/")


def scan_script(parsed: ParsedFile) -> Iterator[Violation]:
    if is_frontend(parsed.path) or AXIOS_DEFAULT_TIMEOUT in parsed.text:
        return
    for node, callee, arguments in calls_of(parsed.root, "call_expression"):
        call = None if is_unknown_or_relative(arguments) else script_call(callee, arguments)
        if call is not None and lacks_bound(arguments, call):
            yield Violation(node, callee, call)
