from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.checks.testing.script_scopes import ScriptResolution, test_callbacks
from pristine.syntax.calls import calls_of
from pristine.syntax.parsing import ParsedFile, all_nodes, node_text

EXPECT = frozenset({"expect", "vitest.expect", "@jest/globals.expect"})
ASSERT = frozenset({"assert", "assert/strict", "node:assert", "node:assert/strict"})
MATCHERS = frozenset({"toBe", "toEqual"})
COMPARISONS = frozenset({"equal", "strictEqual"})
PAIR_SIZE = 2
LITERALS = frozenset(
    {
        "number",
        "string",
        "string_fragment",
        "escape_sequence",
        "true",
        "false",
        "null",
        "undefined",
        "unary_expression",
        "parenthesized_expression",
        "array",
        "object",
        "pair",
        "property_identifier",
    }
)


def unwrap(node: Node) -> Node:
    return (
        unwrap(node.named_children[0])
        if node.type == "parenthesized_expression" and node.named_child_count == 1
        else node
    )


def operands(call: Node, arguments: list[Node], resolution: ScriptResolution) -> tuple[Node, Node] | None:
    function = call.child_by_field_name("function")
    if function is None:
        return None
    name = resolution.qualified(call)
    if any(name == f"{module}.{method}" for module in ASSERT for method in COMPARISONS) and len(arguments) >= PAIR_SIZE:
        return unwrap(arguments[0]), unwrap(arguments[1])
    receiver = function.child_by_field_name("object")
    matcher = node_text(function.child_by_field_name("property"))
    if (
        matcher not in MATCHERS
        or receiver is None
        or receiver.type != "call_expression"
        or len(arguments) != 1
        or resolution.qualified(receiver) not in EXPECT
    ):
        return None
    expected = receiver.child_by_field_name("arguments")
    if expected is None or expected.named_child_count != 1:
        return None
    return unwrap(expected.named_children[0]), unwrap(arguments[0])


def literal_tokens(node: Node) -> list[tuple[str, str | None]]:
    return [
        (
            item.type,
            node_text(item.child_by_field_name("operator")) or (node_text(item) if not item.named_children else None),
        )
        for item in all_nodes(node)
    ]


def same_value(left: Node, right: Node) -> bool:
    if left.type == right.type == "identifier":
        return node_text(left) == node_text(right)
    if any(node.type not in LITERALS for side in (left, right) for node in all_nodes(side)):
        return False
    return literal_tokens(left) == literal_tokens(right)


def assertion_problem(call: Node, arguments: list[Node], resolution: ScriptResolution) -> str | None:
    pair = operands(call, arguments, resolution)
    function = call.child_by_field_name("function")
    deep = function is not None and node_text(function.child_by_field_name("property")) == "toEqual"
    if pair is not None and (deep or pair[0].type not in {"array", "object"}) and same_value(*pair):
        return f"both sides of the assertion are the same expression '{node_text(pair[0])}'"
    return None


def typescript_dependent_assertions(parsed: ParsedFile) -> Iterator[tuple[Node, str]]:
    resolution = ScriptResolution()
    calls = (item for test in test_callbacks(parsed, resolution) for item in calls_of(test, "call_expression"))
    for call, _, arguments in calls:
        if (problem := assertion_problem(call, arguments, resolution)) is not None:
            yield call, problem
