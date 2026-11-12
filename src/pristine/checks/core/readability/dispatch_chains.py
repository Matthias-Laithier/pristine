import re
from collections import Counter
from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding, Severity
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.nodes import COMMENT_KINDS, IF_KINDS
from pristine.syntax.parsing import ParsedFile, line_of, node_text

CHECK_ID = "STR-8"
DISPATCH_CASE_MINIMUM = 3
SUBJECT_PREVIEW_LENGTH = 40
EQUALITY_OPERATORS = frozenset({"==", "===", "is"})
DISJUNCTION_OPERATORS = frozenset({"||", "or"})
COMPARISON_KINDS = frozenset({"binary_expression", "comparison_operator"})
DISJUNCTION_KINDS = frozenset({"binary_expression", "boolean_operator"})
GROUPING_KIND = "parenthesized_expression"
ELIF_KIND = "elif_clause"
ELSE_KIND = "else"
EXEMPT_SUBJECT_PREFIXES = ("typeof ",)
CONSTANT_PATTERN = re.compile(
    r"-?\s*\d[\w.]*|\"(?:[^\"\\$]|\\.)*\"|'(?:[^'\\$]|\\.)*'|`[^`$]*`"
    r"|(?:\w+\.)*(?:[A-Z]\w*\.\w+|[A-Z][A-Z0-9_]+)"
)
SWITCH_LANGUAGES = frozenset({"python", *SCRIPT_LANGUAGES})
SWITCH_KINDS = frozenset({"switch_statement", "match_statement"})
CASE_KINDS = frozenset({"switch_case", "case_clause"})
LABEL_FIELD = "value"
LABEL_KINDS = frozenset({"case_pattern"})
LABEL_WRAPPER_KINDS = LABEL_KINDS | frozenset({"union_pattern", "expression_list"})
GUARD_KINDS = frozenset({"if_clause"})
CHAIN_FIX = (
    "replace it with a dict literal mapping each value to its handler, owned by this module, raising on unknown values"
)
SWITCH_FIX = (
    "prefer a dict literal mapping each value to its handler, owned by this module, raising on unknown values, "
    "unless an exhaustive match is clearer"
)


def is_constant(node: Node) -> bool:
    return CONSTANT_PATTERN.fullmatch((node_text(ungrouped(node)) or "").strip()) is not None


def is_operation(node: Node, kinds: frozenset[str], operators: frozenset[str]) -> bool:
    tokens = {child.type for child in node.children if not child.is_named}
    return node.type in kinds and bool(tokens) and tokens <= operators


def operands(node: Node) -> list[Node]:
    return [child for child in node.named_children if child.type not in COMMENT_KINDS]


def ungrouped(node: Node) -> Node:
    while node.type == GROUPING_KIND and len(operands(node)) == 1:
        node = operands(node)[0]
    return node


def compared_subject(node: Node) -> str | None:
    sides = operands(node)
    if not is_operation(node, COMPARISON_KINDS, EQUALITY_OPERATORS) or sorted(map(is_constant, sides)) != [False, True]:
        return None
    subject = " ".join((node_text(next(side for side in sides if not is_constant(side))) or "").split())
    return None if subject.startswith(EXEMPT_SUBJECT_PREFIXES) else subject


def branch_subject(condition: Node) -> str | None:
    node = ungrouped(condition)
    if not is_operation(node, DISJUNCTION_KINDS, DISJUNCTION_OPERATORS):
        return compared_subject(node)
    subjects = {branch_subject(side) for side in operands(node)}
    return subjects.pop() if len(subjects) == 1 else None


def else_if_of(node: Node) -> Node | None:
    children = node.children
    after_else = (children[index + 1] for index in range(len(children) - 1) if children[index].type == ELSE_KIND)
    alternative = node.child_by_field_name("alternative") or next(after_else, None)
    if alternative is None or alternative.type in IF_KINDS:
        return alternative
    inner = operands(alternative)
    return inner[0] if len(inner) == 1 and inner[0].type in IF_KINDS else None


def chain_branches(head: Node) -> Iterator[Node]:
    node: Node | None = head
    while node is not None:
        yield node
        yield from (child for child in node.children_by_field_name("alternative") if child.type == ELIF_KIND)
        node = else_if_of(node)


def chain_finding(parsed: ParsedFile, head: Node) -> Finding | None:
    conditions = (branch.child_by_field_name("condition") for branch in chain_branches(head))
    subjects = Counter(filter(None, (branch_subject(condition) for condition in conditions if condition is not None)))
    if not subjects or max(subjects.values()) < DISPATCH_CASE_MINIMUM:
        return None
    subject, count = subjects.most_common(1)[0]
    message = f"if/else-if chain compares '{subject[:SUBJECT_PREVIEW_LENGTH]}' to {count} constants; {CHAIN_FIX}"
    return Finding(parsed.path, line_of(head), CHECK_ID, Severity.ERROR, message)


def label_leaves(label: Node) -> list[Node]:
    if label.type not in LABEL_WRAPPER_KINDS:
        return [label]
    return [leaf for child in operands(label) for leaf in label_leaves(child)]


def is_constant_case(case: Node) -> bool:
    value = case.child_by_field_name(LABEL_FIELD)
    labels = ([] if value is None else [value]) + [child for child in case.named_children if child.type in LABEL_KINDS]
    leaves = [leaf for label in labels for leaf in label_leaves(label)]
    is_guarded = any(child.type in GUARD_KINDS for child in case.named_children)
    has_work = len(operands(case)) > len(labels)
    return bool(leaves) and has_work and not is_guarded and all(is_constant(leaf) for leaf in leaves)


def switch_finding(parsed: ParsedFile, switch: Node) -> Finding | None:
    body = switch.child_by_field_name("body")
    candidates = switch.named_children + ([] if body is None else body.named_children)
    count = sum(1 for case in candidates if case.type in CASE_KINDS and is_constant_case(case))
    if count < DISPATCH_CASE_MINIMUM:
        return None
    message = f"{switch.type} dispatches on {count} constant cases; {SWITCH_FIX}"
    return Finding(parsed.path, line_of(switch), CHECK_ID, Severity.WARNING, message)


def check_dispatch_chains(parsed: ParsedFile) -> list[Finding]:
    if_nodes = parsed.nodes_of(*IF_KINDS)
    else_ifs = {else_if.start_byte for node in if_nodes if (else_if := else_if_of(node)) is not None}
    chains = [chain_finding(parsed, node) for node in if_nodes if node.start_byte not in else_ifs]
    switch_kinds = SWITCH_KINDS if parsed.language in SWITCH_LANGUAGES else frozenset()
    switches = [switch_finding(parsed, node) for node in parsed.nodes_of(*switch_kinds)]
    return [finding for finding in chains + switches if finding is not None]


CHECK = FileCheck(
    check_id=CHECK_ID,
    title="Value Dispatch",
    summary=f"Dispatch on {DISPATCH_CASE_MINIMUM}+ constants: if/else-if chain (error), switch or match (warning).",
    run=check_dispatch_chains,
)
