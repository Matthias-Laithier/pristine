from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.checks.registry import FileCheck, register_file_check
from pristine.reports.findings import Finding, Severity
from pristine.syntax.calls import callee_of
from pristine.syntax.parsing import ParsedFile, all_nodes, function_name, is_async, line_of
from pristine.syntax.python_calls import EXTERNAL_CALLS, import_bindings, qualified_callee
from pristine.syntax.syntax_kinds import NESTED_SCOPE_KINDS

RULE_ID = "BS-13"
BLOCKING_CALLS = frozenset(EXTERNAL_CALLS) | {"time.sleep", "psycopg2.connect"}
OFFLOAD_CALLS = frozenset({"asyncio.to_thread", "anyio.to_thread.run_sync"})
EXECUTOR_METHOD = ".run_in_executor"
FUNCTION_KIND = "function_definition"


def is_offload(callee: str, qualified: str | None) -> bool:
    return qualified in OFFLOAD_CALLS or callee.endswith(EXECUTOR_METHOD)


def blocking_calls(body: Node, bindings: dict[str, str]) -> Iterator[tuple[Node, str]]:
    pending = list(body.named_children)
    while pending:
        node = pending.pop()
        callee = callee_of(node)
        qualified = qualified_callee(callee, bindings) if node.type == "call" else None
        if node.type in NESTED_SCOPE_KINDS or is_offload(callee, qualified):
            continue
        if qualified in BLOCKING_CALLS:
            yield node, callee
        pending.extend(node.named_children)


def async_function_findings(path: str, function: Node, bindings: dict[str, str]) -> Iterator[Finding]:
    name = function_name(function)
    body = function.child_by_field_name("body")
    for call, callee in [] if body is None else blocking_calls(body, bindings):
        message = (
            f"'{callee}' blocks the event loop inside async function '{name}'; "
            "await an async API, or offload the call with asyncio.to_thread"
        )
        yield Finding(path, line_of(call), RULE_ID, Severity.ERROR, message)


def check_async_blocking(parsed: ParsedFile) -> list[Finding]:
    if parsed.language != "python":
        return []
    bindings = import_bindings(parsed)
    functions = [node for node in all_nodes(parsed) if node.type == FUNCTION_KIND and is_async(node)]
    findings = (async_function_findings(parsed.path, function, bindings) for function in functions)
    return sorted((finding for group in findings for finding in group), key=lambda finding: finding.line)


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Python blocking calls made directly in an async def: time.sleep, requests, urlopen, subprocess, "
            "smtplib, socket.create_connection, and psycopg2.connect. Calls offloaded to a thread are exempt."
        ),
        run=check_async_blocking,
    )
)
