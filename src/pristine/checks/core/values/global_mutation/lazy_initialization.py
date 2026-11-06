from collections.abc import Iterator

from tree_sitter import Node

from pristine.checks.core.values.global_mutation.scopes import (
    COMPARISON_KINDS,
    SCOPE_KINDS,
    is_name,
    operator_tokens,
    scope_of,
    unparenthesized,
)
from pristine.checks.core.values.global_mutation.writes import Mutation
from pristine.syntax.parsing import all_nodes

NEGATION_KINDS = frozenset({"not_operator", "unary_expression"})
NEGATION_OPERATORS = frozenset({"not", "!"})
EQUALITY_OPERATORS = frozenset({"is", "==", "==="})
INEQUALITY_OPERATORS = frozenset({"is not", "!=", "!=="})
BLOCK_KINDS = frozenset({"block", "statement_block", "module", "program"})
EMPTY_KINDS = frozenset({"none", "null", "undefined"})
ASSIGNMENT_KINDS = frozenset({"assignment", "assignment_expression", "augmented_assignment_expression"})


def compares_with_empty(condition: Node, name: str, operators: frozenset[str]) -> bool:
    tokens = operator_tokens(condition)
    if condition.type not in COMPARISON_KINDS or not operators & tokens:
        return False
    operands = [unparenthesized(child) for child in condition.named_children]
    has_empty = any(operand is not None and operand.type in EMPTY_KINDS for operand in operands)
    return has_empty and any(is_name(operand, name) for operand in operands)


def tests_emptiness(condition: Node | None, name: str) -> bool:
    condition = unparenthesized(condition)
    if condition is None:
        return False
    tokens = operator_tokens(condition)
    if condition.type in NEGATION_KINDS and NEGATION_OPERATORS & tokens:
        return is_name(condition.named_children[-1], name)
    return compares_with_empty(condition, name, EQUALITY_OPERATORS)


def tests_presence(condition: Node | None, name: str) -> bool:
    condition = unparenthesized(condition)
    if condition is None:
        return False
    return is_name(condition, name) or compares_with_empty(condition, name, INEQUALITY_OPERATORS)


def guarding_conditions(node: Node) -> Iterator[Node]:
    child, parent = node, node.parent
    while parent is not None and parent.type not in SCOPE_KINDS:
        condition = parent.child_by_field_name("condition")
        if (
            parent.type == "if_statement"
            and condition is not None
            and parent.child_by_field_name("consequence") == child
        ):
            yield condition
        child, parent = parent, parent.parent


def exits_when_present(node: Node, scope: Node, name: str) -> bool:
    consequence = node.child_by_field_name("consequence")
    if node.type != "if_statement" or consequence is None:
        return False
    exits = (each for each in all_nodes(consequence) if each.type == "return_statement" and scope_of(each) == scope)
    return tests_presence(node.child_by_field_name("condition"), name) and any(exits)


def statement_of(node: Node) -> Node:
    while node.parent is not None and node.parent.type not in BLOCK_KINDS:
        node = node.parent
    return node


def assigns(node: Node, name: str) -> bool:
    targets = (each.child_by_field_name("left") for each in all_nodes(node) if each.type in ASSIGNMENT_KINDS)
    return any(is_name(target, name) for target in targets)


def first_write_after_guard(statement: Node, scope: Node, name: str) -> bool:
    block = statement.parent
    earlier = [] if block is None else block.named_children[: block.named_children.index(statement)]
    guards = [index for index, node in enumerate(earlier) if exits_when_present(node, scope, name)]
    return bool(guards) and not any(assigns(node, name) for node in earlier[guards[-1] + 1 :])


def is_lazy_initialization(mutation: Mutation) -> bool:
    if any(tests_emptiness(condition, mutation.name) for condition in guarding_conditions(mutation.node)):
        return True
    scope = scope_of(mutation.node)
    return scope is not None and first_write_after_guard(statement_of(mutation.node), scope, mutation.name)
