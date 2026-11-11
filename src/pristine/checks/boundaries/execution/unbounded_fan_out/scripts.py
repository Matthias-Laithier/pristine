from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.clients.script_calls import (
    enclosing_function,
    is_shadowed,
    qualified_script_call,
    script_bindings,
)
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.syntax.calls import callee_of, calls_of
from pristine.syntax.nodes import FUNCTION_KINDS
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text

SIZE_KEYS = frozenset({"limit", "size", "pageSize", "take", "maxResults", "count"})


def scope_nodes(root: Node) -> list[Node]:
    pending = [root]
    nodes = []
    while pending:
        node = pending.pop()
        nodes.append(node)
        pending.extend(child for child in node.named_children if child.type not in FUNCTION_KINDS)
    return nodes


def imported_load(value: Node | None, bindings: dict[str, str]) -> bool:
    if value is None or value.type != "await_expression" or not value.named_children:
        return False
    call = value.named_children[0]
    if call.type != "call_expression" or qualified_script_call(call, bindings) is None:
        return False
    keys = {node_text(node.child_by_field_name("key")) for node in all_nodes(call) if node.type == "pair"}
    arguments = call.child_by_field_name("arguments")
    is_sized = arguments is not None and any(argument.type == "number" for argument in arguments.named_children)
    return not is_sized and not (keys & SIZE_KEYS)


def loaded_collection(mapped: Node, name: str, bindings: dict[str, str]) -> bool:
    scope = enclosing_function(mapped)
    if scope is None:
        return False
    parameters = scope.child_by_field_name("parameters")
    if parameters is not None and any(node_text(node) == name for node in all_nodes(parameters)):
        return False
    assignments = [
        node
        for node in scope_nodes(scope.child_by_field_name("body") or scope)
        if node.type in {"variable_declarator", "assignment_expression"}
        and node_text(node.child_by_field_name("name") or node.child_by_field_name("left")) == name
    ]
    return (
        bool(assignments)
        and any(node.start_byte < mapped.start_byte for node in assignments)
        and all(
            imported_load(node.child_by_field_name("value") or node.child_by_field_name("right"), bindings)
            for node in assignments
        )
    )


def fanned_map(arguments: list[Node]) -> tuple[Node, str] | None:
    if len(arguments) != 1 or arguments[0].type != "call_expression":
        return None
    mapped = arguments[0]
    member = mapped.child_by_field_name("function")
    receiver = None if member is None else member.child_by_field_name("object")
    if member is None or receiver is None or receiver.type != "identifier":
        return None
    if node_text(member.child_by_field_name("property")) != "map":
        return None
    callbacks = mapped.child_by_field_name("arguments")
    callback = None if callbacks is None or not callbacks.named_children else callbacks.named_children[0]
    if (
        callback is None
        or callback.type not in FUNCTION_KINDS
        or not any(child.type == "async" for child in callback.children)
    ):
        return None
    body = callback.child_by_field_name("body")
    if body is None or not any(node.type == "await_expression" for node in scope_nodes(body)):
        return None
    return mapped, node_text(receiver) or ""


def callback_uses_limiter(mapped: Node, bindings: dict[str, str]) -> bool:
    factories = {name for name, target in bindings.items() if target == "p-limit/default"}
    root = mapped
    while root.parent is not None:
        root = root.parent
    limiters = {
        node_text(node.child_by_field_name("name")) or ""
        for node in all_nodes(root)
        if node.type == "variable_declarator"
        and (value := node.child_by_field_name("value")) is not None
        and value.type == "call_expression"
        and callee_of(value) in factories
        and not is_shadowed(value, callee_of(value), include_imports=False)
    }
    arguments = mapped.child_by_field_name("arguments")
    callback = None if arguments is None or not arguments.named_children else arguments.named_children[0]
    return callback is not None and any(
        callee_of(call) in limiters for call in all_nodes(callback) if call.type == "call_expression"
    )


def script_fan_out(parsed: ParsedFile) -> list[Finding]:
    if is_test_path(PurePath(parsed.path)):
        return []
    bindings = script_bindings(parsed)
    if any(target.startswith(("@temporalio/", "@mistralai/workflows/")) for target in bindings.values()):
        return []
    findings = []
    for call, callee, arguments in calls_of(parsed, "call_expression"):
        mapped = fanned_map(arguments) if callee == "Promise.all" and not is_shadowed(call, "Promise") else None
        if (
            mapped is not None
            and loaded_collection(mapped[0], mapped[1], bindings)
            and not callback_uses_limiter(mapped[0], bindings)
        ):
            message = f"'{callee_of(call)}' fans out over '{mapped[1]}' with no concurrency bound; use a bounded concurrency limiter"
            findings.append(Finding(parsed.path, line_of(call), "BS-14", Severity.WARNING, message))
    return findings
