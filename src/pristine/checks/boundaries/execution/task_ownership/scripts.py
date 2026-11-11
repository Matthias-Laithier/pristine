lazy from tree_sitter import Node

from pristine.clients.script_calls import (
    qualified_script_call,
    script_bindings,
)
from pristine.reports.findings import Finding, Severity
from pristine.syntax.calls import callee_of
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of

HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "request"})
FS_METHODS = frozenset(
    {
        "readFile",
        "writeFile",
        "appendFile",
        "readdir",
        "stat",
        "lstat",
        "access",
        "unlink",
        "mkdir",
        "rm",
        "rename",
        "copyFile",
        "open",
    }
)
ASYNC_TARGETS = (
    frozenset({"node-fetch/default", "undici/fetch"})
    | {f"{module}/{method}" for module in ("fs/promises", "node:fs/promises") for method in FS_METHODS}
    | {
        f"{module}/{method}"
        for module in ("timers/promises", "node:timers/promises")
        for method in ("setTimeout", "setImmediate")
    }
)


def is_known_operation(call: Node, bindings: dict[str, str]) -> bool:
    target = qualified_script_call(call, bindings)
    if target is None:
        return False
    normalized = target.replace("/default/", "/")
    return (
        normalized in ASYNC_TARGETS
        or target == "axios/default"
        or (normalized.startswith("axios/") and normalized.removeprefix("axios/") in HTTP_METHODS)
    )


def dropped_operations(parsed: ParsedFile) -> list[Finding]:
    bindings = script_bindings(parsed)
    return [
        Finding(
            parsed.path,
            line_of(call),
            "BS-8",
            Severity.ERROR,
            f"'{callee_of(call)}(...)' drops a known asynchronous operation; await, return, or retain and handle its promise",
        )
        for call in all_nodes(parsed)
        if call.type == "call_expression"
        and call.parent is not None
        and call.parent.type == "expression_statement"
        and is_known_operation(call, bindings)
    ]
