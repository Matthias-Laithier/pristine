import re
from collections.abc import Iterator

from tree_sitter import Node

from pristine.calls import callee_of
from pristine.checks.registry import FileCheck, register_file_check
from pristine.findings import Finding, Severity
from pristine.parsing import ParsedFile, all_nodes, line_of, node_text
from pristine.python_tests import is_python_test_module, is_test_definition

RULE_ID = "TST-7"
EQUALITY = "=="
IDENTITY = "is"
PAIR_SIZE = 2
UNITTEST_COMPARISONS = {"self.assertEqual": EQUALITY, "self.assertIs": IDENTITY}
RAISING_CONTEXTS = re.compile(r"(\w+\.)*(raises|assertRaises\w*)")
STATEFUL_CALLEES = re.compile(
    r"(.*\.)?(next|anext|pop|popleft|popitem|read|readline|recv|receive|send|get_nowait|uuid\d|now|utcnow|today"
    r"|time|monotonic|perf_counter|random|randint|choice|sample|shuffle|token_hex|urandom)"
)
PROPERTY_NAME = re.compile(
    r"(^|_)(eq|equal[a-z]*|reflexiv[a-z]*|identity|same|hash[a-z]*|determinis[a-z]*|idempoten[a-z]*|stab[a-z]*"
    r"|consistent|repeatable|reproducible|cach[a-z]*|memoized|singleton|pure|cop(y|ies))(_|$)"
)
CALL_KIND = "call"
AWAIT_KIND = "await"
EVALUATING_KINDS = frozenset({CALL_KIND, AWAIT_KIND})
WRAPPER_KINDS = frozenset({"expression_statement", "parenthesized_expression"})
BLOCK_KINDS = frozenset({"block", "module"})
SAME_SIDES = "both sides of the assertion are the same expression '{text}'"
SAME_CALL = "the expected value '{text}' is computed by the same call as the actual value"
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


def is_computed_by_production(side: Node, local_names: frozenset[str]) -> bool:
    nodes = list(all_nodes(side))
    callees = [callee_of(node) for node in nodes if node.type == CALL_KIND]
    is_local = any(callee.removeprefix("self.") in local_names for callee in callees)
    is_constructor = any(callee.rsplit(".", 1)[-1][:1].isupper() for callee in callees)
    is_stateful = any(STATEFUL_CALLEES.fullmatch(callee) for callee in callees)
    return not (is_local or is_constructor or is_stateful or any(node.type == AWAIT_KIND for node in nodes))


def is_shared_call(actual: Node, expected: Node, assertion: Node) -> bool:
    statement = assertion if assertion.parent is None or assertion.parent.type in BLOCK_KINDS else assertion.parent
    previous = statement.prev_named_sibling
    assignment = None if previous is None else unwrapped(previous)
    if actual.type != CALL_KIND or expected.type != "identifier" or assignment is None:
        return False
    target = assignment.child_by_field_name("left")
    source = assignment.child_by_field_name("right")
    is_assigned = assignment.type == "assignment" and target is not None and normalized(target) == normalized(expected)
    return is_assigned and source is not None and normalized(source) == normalized(actual)


def dependent_assertion(node: Node, local_names: frozenset[str]) -> str | None:
    pair = compared_pair(node)
    if pair is None or is_in_raising_context(node):
        return None
    left, right, operator = pair
    if normalized(left) == normalized(right):
        is_plain = not any(side.type in EVALUATING_KINDS for side in all_nodes(left))
        return SAME_SIDES.format(text=normalized(left)) if is_plain else None
    for actual, expected in ((left, right), (right, left)):
        is_dependent = is_shared_call(actual, expected, node) and is_computed_by_production(actual, local_names)
        if operator == EQUALITY and is_dependent:
            return SAME_CALL.format(text=normalized(expected))
    return None


def has_property_name(test: Node) -> bool:
    name = node_text(test.child_by_field_name("name")) or ""
    return PROPERTY_NAME.search(name.lower()) is not None


def dependent_assertions(root: Node) -> Iterator[tuple[Node, str]]:
    definitions = [node for node in all_nodes(root) if node.type == "function_definition"]
    local_names = frozenset(node_text(node.child_by_field_name("name")) or "" for node in definitions)
    tests = [node for node in definitions if is_test_definition(node) and not has_property_name(node)]
    for node in (node for test in tests for node in all_nodes(test)):
        problem = dependent_assertion(node, local_names)
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
            "Python test functions asserting == or is between two identical call-free expressions, or asserting == "
            "against a variable assigned on the line before by the identical call. Constructors, helpers defined in "
            "the file, stateful calls, awaits, pytest.raises blocks, and tests named for equality or determinism "
            "properties are exempt."
        ),
        run=check_dependent_oracles,
    )
)
