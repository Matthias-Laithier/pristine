from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding, Severity
from pristine.syntax.calls import callee_of
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text
from pristine.syntax.python_calls import import_bindings, qualified_callee
from pristine.syntax.python_tests import is_python_test_module, is_test_definition

RULE_ID = "TST-7"
EQUALITY = "=="
IDENTITY = "is"
PAIR_SIZE = 2
UNITTEST_COMPARISONS = {"self.assertEqual": EQUALITY, "self.assertIs": IDENTITY}
CALL_KIND = "call"
RAISING_FUNCTIONS = frozenset({"pytest.raises"})
RAISING_METHODS = frozenset({"self.assertRaises", "self.assertRaisesRegex"})
TEST_CASE_CLASSES = frozenset({"unittest.TestCase", "unittest.IsolatedAsyncioTestCase"})
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


def is_test_case(definition: Node, bindings: dict[str, str], classes: dict[str, Node]) -> bool:
    superclasses = definition.child_by_field_name("superclasses")
    for base in [] if superclasses is None else superclasses.named_children:
        name = normalized(base)
        local = classes.get(name)
        if qualified_callee(name, bindings) in TEST_CASE_CLASSES:
            return True
        if local is not None and local is not definition and is_test_case(local, bindings, classes):
            return True
    return False


def enclosing_class(node: Node) -> Node | None:
    holder = node.parent
    while holder is not None and holder.type != "class_definition":
        holder = holder.parent
    return holder


class RaisingContexts:
    def __init__(self, source: Node | ParsedFile) -> None:
        self.bindings = import_bindings(source)
        definitions = (node for node in all_nodes(source) if node.type == "class_definition")
        self.classes = {node_text(node.child_by_field_name("name")) or "": node for node in definitions}

    def opens(self, statement: Node) -> bool:
        items = (item for item in all_nodes(statement.named_children[0]) if item.type == "with_item")
        values = (item.child_by_field_name("value") for item in items)
        return any(value is not None and value.type == CALL_KIND and self.raises(value) for value in values)

    def raises(self, call: Node) -> bool:
        callee = callee_of(call)
        if qualified_callee(callee, self.bindings) in RAISING_FUNCTIONS:
            return True
        definition = enclosing_class(call) if callee in RAISING_METHODS else None
        return definition is not None and is_test_case(definition, self.bindings, self.classes)

    def encloses(self, node: Node) -> bool:
        holder = node.parent
        while holder is not None and not is_test_definition(holder):
            if holder.type == "with_statement" and self.opens(holder):
                return True
            holder = holder.parent
        return False


def cannot_differ(side: Node, operator: str) -> bool:
    if operator == IDENTITY:
        return side.type in IDENTITY_KINDS
    return all(node.type in LITERAL_KINDS for node in all_nodes(side) if node.is_named)


def dependent_assertion(node: Node, contexts: RaisingContexts) -> str | None:
    pair = compared_pair(node)
    if pair is None or contexts.encloses(node):
        return None
    left, right, operator = pair
    if normalized(left) != normalized(right) or not cannot_differ(left, operator):
        return None
    return SAME_SIDES.format(text=normalized(left))


def dependent_assertions(source: Node | ParsedFile) -> Iterator[tuple[Node, str]]:
    contexts = RaisingContexts(source)
    tests = [node for node in all_nodes(source) if node.type == "function_definition" and is_test_definition(node)]
    for node in (node for test in tests for node in all_nodes(test)):
        problem = dependent_assertion(node, contexts)
        if problem is not None:
            yield node, problem


def check_dependent_oracles(parsed: ParsedFile) -> list[Finding]:
    if not is_python_test_module(parsed):
        return []
    return [
        Finding(parsed.path, line_of(node), RULE_ID, Severity.ERROR, f"{problem}, so it cannot fail; {FIX}")
        for node, problem in dependent_assertions(parsed)
    ]


CHECK = FileCheck(
    rule_id=RULE_ID,
    title="No Tautological Assertions",
    summary=(
        "Python test functions asserting == between two identical literals, or is between two identical names "
        "or singletons (True, False, None, ...). Assertions inside pytest.raises blocks, or assertRaises blocks of unittest TestCase classes, are exempt."
    ),
    run=check_dependent_oracles,
)
