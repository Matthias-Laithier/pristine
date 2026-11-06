lazy from tree_sitter import Node

from pristine.syntax.parsing import all_nodes, node_text
from pristine.syntax.syntax_kinds import FUNCTION_KINDS

SCOPE_KINDS = FUNCTION_KINDS | {"generator_function"}
COMPARISON_KINDS = frozenset({"comparison_operator", "binary_expression"})


def scope_of(node: Node) -> Node | None:
    parent = node.parent
    while parent is not None and parent.type not in SCOPE_KINDS:
        parent = parent.parent
    return parent


def names_in(node: Node | None) -> set[str]:
    nodes = [] if node is None else all_nodes(node)
    return {node_text(each) or "" for each in nodes if each.type == "identifier"}


def unparenthesized(node: Node | None) -> Node | None:
    while node is not None and node.type == "parenthesized_expression" and node.named_children:
        node = node.named_children[0]
    return node


def is_name(node: Node | None, name: str) -> bool:
    node = unparenthesized(node)
    return node is not None and node.type == "identifier" and node_text(node) == name


def operator_tokens(node: Node) -> set[str]:
    return {child.type for child in node.children if not child.is_named}
