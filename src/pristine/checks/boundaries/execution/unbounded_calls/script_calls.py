from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.checks.boundaries.execution.unbounded_calls.calls import Violation
from pristine.reports.findings import Severity
from pristine.syntax.calls import BoundedCall, calls_of, has_unknown_argument
from pristine.syntax.parsing import ParsedFile, all_nodes, node_text

AXIOS = "axios"
AXIOS_FIX = "set timeout in the config, or call an axios.create({ timeout }) instance"
AXIOS_DEFAULT_TIMEOUT = "axios.defaults.timeout"
AXIOS_CONFIG_POSITIONS = {"get": 1, "delete": 1, "head": 1, "options": 1, "post": 2, "put": 2, "patch": 2, "request": 0}
CLIENT_DIRECTIVE = "use client"
BROWSER_FRAMEWORKS = ("react", "react-dom", "preact", "vue", "svelte", "solid-js", "@angular/core")
JSX_KINDS = frozenset({"jsx_element", "jsx_self_closing_element", "jsx_fragment"})
MODULE_LOADER = "require"
COMMENT = "comment"
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


def string_value(node: Node | None) -> str | None:
    return None if node is None or node.type != "string" else (node_text(node) or "").strip(QUOTES)


def imported_module(node: Node) -> str | None:
    if node.type == "import_statement":
        return string_value(node.child_by_field_name("source"))
    arguments = node.child_by_field_name("arguments")
    is_require = node.type == "call_expression" and node_text(node.child_by_field_name("function")) == MODULE_LOADER
    return string_value(arguments.named_children[0]) if is_require and arguments and arguments.named_children else None


def is_browser_node(node: Node) -> bool:
    module = imported_module(node) or ""
    is_framework = any(module == framework or module.startswith(f"{framework}/") for framework in BROWSER_FRAMEWORKS)
    return is_framework or node.type in JSX_KINDS


def has_client_directive(root: Node) -> bool:
    first = next((child for child in root.named_children if child.type != COMMENT), None)
    directive = None if first is None or first.type != "expression_statement" else first.named_children[0]
    return string_value(directive) == CLIENT_DIRECTIVE


def is_browser_code(source: Node | ParsedFile) -> bool:
    root = source.root if isinstance(source, ParsedFile) else source
    return has_client_directive(root) or any(map(is_browser_node, all_nodes(source)))


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
    if is_browser_code(parsed) or AXIOS_DEFAULT_TIMEOUT in parsed.text:
        return
    for node, callee, arguments in calls_of(parsed, "call_expression"):
        call = None if is_unknown_or_relative(arguments) else script_call(callee, arguments)
        if call is not None and lacks_bound(arguments, call):
            yield Violation(node, callee, call)
