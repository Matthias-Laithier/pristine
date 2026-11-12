from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.checks.definitions import FileCheck
from pristine.clients.script_calls import (
    ScriptScopes,
    enclosing_function,
    qualified_script_call,
    script_bindings,
)
from pristine.reports.findings import Finding, Severity
from pristine.syntax.calls import callee_of
from pristine.syntax.nodes import NESTED_SCOPE_KINDS
from pristine.syntax.parsing import ParsedFile, all_nodes, function_name, is_async, line_of
from pristine.syntax.python_calls import EXTERNAL_CALLS, import_bindings, qualified_callee

CHECK_ID = "SAFE-7"
BLOCKING_CALLS = frozenset(EXTERNAL_CALLS) | {"time.sleep", "psycopg2.connect"}
OFFLOAD_CALLS = frozenset({"asyncio.to_thread", "anyio.to_thread.run_sync"})
EXECUTOR_METHOD = ".run_in_executor"
FUNCTION_KIND = "function_definition"
SYNC_FS_METHODS = frozenset(
    {
        "readFileSync",
        "writeFileSync",
        "appendFileSync",
        "readdirSync",
        "statSync",
        "lstatSync",
        "accessSync",
        "existsSync",
        "unlinkSync",
        "mkdirSync",
        "rmSync",
        "renameSync",
        "copyFileSync",
        "openSync",
        "closeSync",
        "readSync",
        "writeSync",
        "realpathSync",
        "readlinkSync",
        "fsyncSync",
    }
)


def is_script_async(function: Node | None) -> bool:
    return function is not None and any(child.type == "async" for child in function.children)


def script_blocking_findings(parsed: ParsedFile) -> list[Finding]:
    bindings = script_bindings(parsed)
    scopes = ScriptScopes()
    findings = []
    for call in (node for node in all_nodes(parsed) if node.type == "call_expression"):
        function = enclosing_function(call)
        if not is_script_async(function):
            continue
        target = qualified_script_call(call, bindings, scopes)
        module, _, method = (target or "").replace("/default/", "/").partition("/")
        if module in {"fs", "node:fs"} and method in SYNC_FS_METHODS:
            message = (
                f"'{callee_of(call)}' blocks the event loop inside an async function; await a Node fs/promises API"
            )
            findings.append(Finding(parsed.path, line_of(call), CHECK_ID, Severity.ERROR, message))
    return findings


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
        yield Finding(path, line_of(call), CHECK_ID, Severity.ERROR, message)


def check_async_blocking(parsed: ParsedFile) -> list[Finding]:
    if parsed.language in {"javascript", "typescript", "tsx"}:
        return script_blocking_findings(parsed)
    if parsed.language != "python":
        return []
    bindings = import_bindings(parsed)
    functions = [node for node in all_nodes(parsed) if node.type == FUNCTION_KIND and is_async(node)]
    findings = (async_function_findings(parsed.path, function, bindings) for function in functions)
    return sorted((finding for group in findings for finding in group), key=lambda finding: finding.line)


CHECK = FileCheck(
    check_id=CHECK_ID,
    title="Blocking Async Calls",
    summary=(
        "Python blocking calls made directly in an async def: time.sleep, requests, urlopen, subprocess, "
        "smtplib, socket.create_connection, and psycopg2.connect. Calls offloaded to a thread are exempt."
        " JS/TS imported Node fs synchronous IO in async functions; nested synchronous callbacks are exempt."
    ),
    run=check_async_blocking,
)
