import re
from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.checks.registry import FileCheck, register_file_check
from pristine.reports.findings import Finding, Severity
from pristine.syntax.calls import callee_of
from pristine.syntax.nodes import NESTED_SCOPE_KINDS
from pristine.syntax.parsing import ParsedFile, all_nodes, is_async, line_of, node_text
from pristine.syntax.python_calls import import_bindings, qualified_callee

RULE_ID = "BS-8"
TASK_FACTORIES = frozenset({"asyncio.create_task", "asyncio.ensure_future"})
LOOP_RECEIVER = re.compile(r"([\w.]*\.)?\w*loop(\(\))?", re.IGNORECASE)
STATEMENT_CONTAINERS = frozenset({"module", "block"})
CANCELLED_ERRORS = frozenset({"asyncio.CancelledError", "asyncio.exceptions.CancelledError"})
BROAD_CATCH = "BaseException"
GROUP_KINDS = frozenset({"tuple", "parenthesized_expression"})
REFERENCE_KINDS = frozenset({"identifier", "attribute", "subscript"})
CLEANUP_KINDS = frozenset({"except_clause", "finally_clause"})
FORMATTING_CALLS = frozenset({"str", "repr", "type"})
LOG_KEYWORD = "exc_info"
NOTE_METHOD = "add_note"
OWN_TASK_HINT = "keep the task and await it, or spawn it in a TaskGroup"
RERAISE_HINT = "re-raise it with a bare 'raise' after the cleanup"


def spawns_task(call: Node, bindings: dict[str, str]) -> bool:
    callee = callee_of(call)
    receiver, _, method = callee.rpartition(".")
    is_loop_spawn = method == "create_task" and LOOP_RECEIVER.fullmatch(receiver) is not None
    return is_loop_spawn or qualified_callee(callee, bindings) in TASK_FACTORIES


def dropped_tasks(parsed: ParsedFile, bindings: dict[str, str]) -> Iterator[Finding]:
    for call in (node for node in all_nodes(parsed) if node.type == "call"):
        is_statement = call.parent is not None and call.parent.type in STATEMENT_CONTAINERS
        if is_statement and spawns_task(call, bindings):
            message = f"'{callee_of(call)}(...)' creates a task and drops its reference; {OWN_TASK_HINT}"
            yield Finding(parsed.path, line_of(call), RULE_ID, Severity.ERROR, message)


def scope_nodes(root: Node) -> Iterator[Node]:
    pending = [root]
    while pending:
        node = pending.pop()
        yield node
        pending.extend(child for child in node.named_children if child.type not in NESTED_SCOPE_KINDS)


def caught_types(caught: Node | None) -> list[Node]:
    if caught is not None and caught.type == "as_pattern":
        caught = caught.named_children[0]
    if caught is None:
        return []
    return caught.named_children if caught.type in GROUP_KINDS else [caught]


def enclosing_nodes(node: Node) -> list[Node]:
    chain = []
    scope = node.parent
    while scope is not None and (not chain or chain[-1].type not in NESTED_SCOPE_KINDS):
        chain.append(scope)
        scope = scope.parent
    return chain


def can_be_cancelled(clause: Node) -> bool:
    chain = enclosing_nodes(clause)
    if not chain or not is_async(chain[-1]) or any(node.type in CLEANUP_KINDS for node in chain):
        return False
    body = chain[0].child_by_field_name("body")
    nodes = [] if body is None else scope_nodes(body)
    return any(is_async(node) or (node.type == "await" and is_awaiting_work(node)) for node in nodes)


def is_awaiting_work(awaited: Node) -> bool:
    return awaited.named_children[0].type not in REFERENCE_KINDS


def names_cancellation(clause: Node, bindings: dict[str, str]) -> bool:
    names = [node_text(caught) for caught in caught_types(clause.child_by_field_name("value"))]
    return any(qualified_callee(name or "", bindings) in CANCELLED_ERRORS for name in names)


def catches_cancellation(clause: Node, bindings: dict[str, str]) -> bool:
    names = [node_text(caught) for caught in caught_types(clause.child_by_field_name("value"))]
    earlier = (
        [] if clause.parent is None else clause.parent.named_children[: clause.parent.named_children.index(clause)]
    )
    is_broad = (not names or BROAD_CATCH in names) and not any(names_cancellation(node, bindings) for node in earlier)
    return (is_broad or names_cancellation(clause, bindings)) and can_be_cancelled(clause)


def uses_caught_value(reference: Node) -> bool:
    parent = reference.parent
    holder = None if parent is None else parent.parent
    if parent is None or holder is None or parent.type == "interpolation":
        return False
    if parent.type == "keyword_argument":
        return (
            reference == parent.child_by_field_name("value")
            and node_text(parent.child_by_field_name("name")) != LOG_KEYWORD
        )
    return parent.type != "argument_list" or callee_of(holder) not in FORMATTING_CALLS


def propagates(clause: Node) -> bool:
    caught = clause.child_by_field_name("value")
    alias = None if caught is None else node_text(caught.child_by_field_name("alias"))
    nodes = list(scope_nodes(clause.named_children[-1]))
    references = [node for node in nodes if node.type == "identifier" and node_text(node) in {alias, NOTE_METHOD}]
    return any(node.type == "raise_statement" for node in nodes) or any(map(uses_caught_value, references))


def swallowed_cancellations(parsed: ParsedFile, bindings: dict[str, str]) -> Iterator[Finding]:
    for clause in (node for node in all_nodes(parsed) if node.type == "except_clause"):
        if catches_cancellation(clause, bindings) and not propagates(clause):
            caught = clause.child_by_field_name("value")
            head = "except" if caught is None else f"except {' '.join((node_text(caught) or '').split())}"
            message = f"'{head}' swallows the task's cancellation; {RERAISE_HINT}"
            yield Finding(parsed.path, line_of(clause), RULE_ID, Severity.ERROR, message)


def check_task_ownership(parsed: ParsedFile) -> list[Finding]:
    if parsed.language != "python":
        return []
    bindings = import_bindings(parsed)
    findings = [*dropped_tasks(parsed, bindings), *swallowed_cancellations(parsed, bindings)]
    return sorted(findings, key=lambda finding: finding.line)


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Python asyncio tasks created and dropped as a bare statement, and except clauses that catch "
            "CancelledError, or BaseException in an async def, without re-raising it."
        ),
        run=check_task_ownership,
    )
)
