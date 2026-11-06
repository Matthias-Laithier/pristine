import re
from collections.abc import Iterator
from dataclasses import dataclass

from tree_sitter import Node

from pristine.checks.registry import FileCheck, register_file_check
from pristine.reports.findings import Finding, Limit
from pristine.syntax.parsing import ParsedFile, function_name, line_of, node_text
from pristine.syntax.syntax_kinds import (
    ANONYMOUS_FUNCTION_KINDS,
    ELSE_CONTAINERS,
    IF_KINDS,
    LEVEL_KINDS,
    NAME_BINDING_KINDS,
    NAMED_FUNCTION_KINDS,
)

RULE_ID = "CR-13"
NESTING_LIMIT = Limit(target=2, hard=3)
TEST_FRAMEWORK_CALL = re.compile(
    r"(describe|context|suite|it|test|bench|beforeEach|afterEach|beforeAll|afterAll)(\.\w+)*(\(.*\))?",
    re.DOTALL,
)


@dataclass(frozen=True)
class Block:
    scope: Node
    depth: int
    node: Node


def is_else_if(node: Node) -> bool:
    parent = node.parent
    if node.type not in IF_KINDS or parent is None:
        return False
    if parent.type in ELSE_CONTAINERS:
        return True
    return parent.type in IF_KINDS and parent.child_by_field_name("alternative") == node


def is_test_framework_callback(node: Node) -> bool:
    arguments = node.parent
    call = arguments.parent if arguments is not None and arguments.type == "arguments" else None
    if call is None or call.type != "call_expression":
        return False
    return TEST_FRAMEWORK_CALL.fullmatch(node_text(call.child_by_field_name("function")) or "") is not None


def opens_function_scope(node: Node) -> bool:
    if node.type in NAMED_FUNCTION_KINDS:
        return True
    is_bound = node.parent is not None and node.parent.type in NAME_BINDING_KINDS
    return node.type in ANONYMOUS_FUNCTION_KINDS and (is_bound or is_test_framework_callback(node))


def added_levels(node: Node) -> int:
    if is_else_if(node):
        return 0
    return int(node.is_named and node.type in LEVEL_KINDS)


def child_entries(node: Node, depth: int, scope: Node) -> Iterator[tuple[Node, int, Node]]:
    for child in node.named_children:
        if opens_function_scope(child):
            yield child, 0, child
        else:
            yield child, depth + added_levels(child), scope


def blocks(root: Node) -> Iterator[Block]:
    pending = [(root, 0, root)]
    while pending:
        node, depth, scope = pending.pop()
        entries = list(child_entries(node, depth, scope))
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
        findings.append(Finding(parsed.path, line_of(block.node), RULE_ID, severity, message))
    return findings


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            f"Control-flow nesting depth per function ({NESTING_LIMIT.describe()}); else-if adds no level, "
            "a comprehension or lambda adds one."
        ),
        run=check_nesting,
    )
)
