import re
from collections.abc import Iterator

from tree_sitter import Node

from pristine.checks.registry import FileCheck, register_file_check
from pristine.reports.findings import Finding, Severity
from pristine.syntax.calls import callee_of
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text
from pristine.syntax.python_tests import is_python_test_module, is_test_definition

RULE_ID = "TST-7"
EQUALITY = "=="
IDENTITY = "is"
PAIR_SIZE = 2
UNITTEST_COMPARISONS = {"self.assertEqual": EQUALITY, "self.assertIs": IDENTITY}
CALL_KIND = "call"
RAISING_CONTEXTS = re.compile(r"(\w+\.)*(raises|assertRaises\w*)")
SINGLETON_KINDS = frozenset({"true", "false", "none", "ellipsis"})
IDENTITY_KINDS = SINGLETON_KINDS | {"identifier"}
LITERAL_KINDS = (
    SINGLETON_KINDS
    | {"integer", "float", "unary_operator", "concatenated_string"}
    | {"string", "string_start", "string_content", "string_end", "escape_sequence"}
    | {"tuple", "list", "set", "dictionary", "pair", "parenthesized_expression"}
)
WRAPPER_KINDS = frozenset({"expression_statement", "parenthesized_expression"})
SAME_SIDES = "both sides of the assertion are the same expression '{text}'"
FIX = "compare against a hand-checked value or an independent invariant derived from the contract"


def normalized(node: Node) -> str:
    return " ".join((node_text(node) or "").split())


def unwrapped(node: Node) -> Node:
    inner = node.named_children
    return unwrapped(inner[0]) if node.type in WRAPPER_KINDS and len(inner) == 1 else node


def assertion_operands(node: Node) -> tuple[list[Node], str | None]:
    if node.type == "assert_statement" and node.named_children:
        condition = unwrapped(node.named_children[0])
        operators = [child.type for child in condition.children if not child.is_named]
        is_comparison = condition.type == "comparison_operator" and len(operators) == 1
        return (condition.named_children, operators[0]) if is_comparison else ([], None)
    arguments = node.child_by_field_name("arguments")
    operator = UNITTEST_COMPARISONS.get(callee_of(node)) if node.type == CALL_KIND else None
    return ([] if arguments is None else arguments.named_children[:PAIR_SIZE]), operator


def compared_pair(node: Node) -> tuple[Node, Node, str] | None:
    operands, operator = assertion_operands(node)
    if operator not in (EQUALITY, IDENTITY) or len(operands) != PAIR_SIZE:
        return None
    return unwrapped(operands[0]), unwrapped(operands[1]), operator


def opens_raising_context(statement: Node) -> bool:
    items = (item for item in all_nodes(statement.named_children[0]) if item.type == "with_item")
    return any(RAISING_CONTEXTS.fullmatch(callee_of(item.child_by_field_name("value") or item)) for item in items)


def is_in_raising_context(node: Node) -> bool:
    holder = node.parent
    while holder is not None and not is_test_definition(holder):
        if holder.type == "with_statement" and opens_raising_context(holder):
            return True
        holder = holder.parent
    return False


def cannot_differ(side: Node, operator: str) -> bool:
    if operator == IDENTITY:
        return side.type in IDENTITY_KINDS
    return all(node.type in LITERAL_KINDS for node in all_nodes(side) if node.is_named)


def dependent_assertion(node: Node) -> str | None:
    pair = compared_pair(node)
    if pair is None or is_in_raising_context(node):
        return None
    left, right, operator = pair
    if normalized(left) != normalized(right) or not cannot_differ(left, operator):
        return None
    return SAME_SIDES.format(text=normalized(left))


def dependent_assertions(root: Node) -> Iterator[tuple[Node, str]]:
    tests = [node for node in all_nodes(root) if node.type == "function_definition" and is_test_definition(node)]
    for node in (node for test in tests for node in all_nodes(test)):
        problem = dependent_assertion(node)
        if problem is not None:
            yield node, problem


def check_dependent_oracles(parsed: ParsedFile) -> list[Finding]:
    if not is_python_test_module(parsed):
        return []
    return [
        Finding(parsed.path, line_of(node), RULE_ID, Severity.ERROR, f"{problem}, so it cannot fail; {FIX}")
        for node, problem in dependent_assertions(parsed.root)
    ]


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Python test functions asserting == between two identical literals, or is between two identical names "
            "or singletons (True, False, None, ...). Assertions inside pytest.raises blocks are exempt."
        ),
        run=check_dependent_oracles,
    )
)
