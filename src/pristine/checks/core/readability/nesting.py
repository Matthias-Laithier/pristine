import re
from collections.abc import Iterator
from dataclasses import dataclass

lazy from tree_sitter import Node

from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding, Limit
from pristine.syntax.nodes import (
    ANONYMOUS_FUNCTION_KINDS,
    ELSE_CONTAINERS,
    IF_KINDS,
    LEVEL_KINDS,
    NAME_BINDING_KINDS,
    NAMED_FUNCTION_KINDS,
    SyntaxNode,
)
from pristine.syntax.parsing import ParsedFile, function_name, line_of, node_text

CHECK_ID = "STR-3"
NESTING_LIMIT = Limit(target=2, hard=3)
TEST_FRAMEWORK_CALL = re.compile(
    r"(describe|context|suite|it|test|bench|beforeEach|afterEach|beforeAll|afterAll)(\.\w+)*(\(.*\))?",
    re.DOTALL,
)


@dataclass(frozen=True)
class Block:
    scope: SyntaxNode
    depth: int
    node: SyntaxNode


def is_else_if(node: Node, parent: Node) -> bool:
    if parent.type in ELSE_CONTAINERS:
        return True
    return parent.type in IF_KINDS and parent.child_by_field_name("alternative") == node


def is_test_framework_callback(arguments: Node) -> bool:
    call = arguments.parent if arguments.type == "arguments" else None
    if call is None or call.type != "call_expression":
        return False
    return TEST_FRAMEWORK_CALL.fullmatch(node_text(call.child_by_field_name("function")) or "") is not None


def opens_function_scope(kind: str, parent: Node) -> bool:
    if kind in NAMED_FUNCTION_KINDS:
        return True
    if kind not in ANONYMOUS_FUNCTION_KINDS:
        return False
    return parent.type in NAME_BINDING_KINDS or is_test_framework_callback(parent)


def added_levels(node: Node, kind: str, parent: Node) -> int:
    if kind not in LEVEL_KINDS:
        return 0
    return int(kind not in IF_KINDS or not is_else_if(node, parent))


def child_entry(child: Node, parent: Node, depth: int, scope: Node) -> tuple[Node, int, Node]:
    kind = child.type
    if opens_function_scope(kind, parent):
        return child, 0, child
    return child, depth + added_levels(child, kind, parent), scope


def blocks(root: Node) -> Iterator[Block]:
    pending = [(root, 0, root)]
    while pending:
        node, depth, scope = pending.pop()
        entries = [child_entry(child, node, depth, scope) for child in node.named_children]
        yield from (
            Block(entry_scope, entry_depth, child) for child, entry_depth, entry_scope in entries if entry_depth > depth
        )
        pending.extend(entries)


def deepest_block_per_scope(root: Node) -> list[Block]:
    deepest: dict[int, Block] = {}
    for block in blocks(root):
        current = deepest.get(block.scope.start_byte)
        if current is None or block.depth > current.depth:
            deepest[block.scope.start_byte] = block
    return list(deepest.values())


def scope_name(scope: Node) -> str:
    if scope.parent is None:
        return "module level code"
    return f"function '{function_name(scope)}'"


def check_nesting(parsed: ParsedFile) -> list[Finding]:
    findings = []
    for block in deepest_block_per_scope(parsed.root):
        severity = NESTING_LIMIT.severity_for(block.depth)
        if severity is None:
            continue
        message = (
            f"{scope_name(block.scope)} nests {block.depth} levels deep ({NESTING_LIMIT.describe()}); "
            "use guard clauses or extract the deepest block into a named helper"
        )
        findings.append(Finding(parsed.path, line_of(block.node), CHECK_ID, severity, message))
    return findings


CHECK = FileCheck(
    check_id=CHECK_ID,
    title="Nesting Depth",
    summary=(
        f"Control-flow nesting depth per function ({NESTING_LIMIT.describe()}); else-if adds no level, "
        "a comprehension or lambda adds one."
    ),
    run=check_nesting,
)
