from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.checks.core.placement.global_placement.references import identifiers
from pristine.syntax.nodes import FUNCTION_KINDS
from pristine.syntax.parsing import node_text

SCOPE_KINDS = FUNCTION_KINDS | {"class_declaration", "class"}


def own_nodes(node: Node) -> Iterator[Node]:
    pending = list(node.named_children)
    while pending:
        child = pending.pop()
        yield child
        if child.type not in SCOPE_KINDS:
            pending.extend(child.named_children)


def parameter_names(node: Node) -> set[str]:
    parameters = node.child_by_field_name("parameters")
    if parameters is None:
        parameter = node.child_by_field_name("parameter")
        return set() if parameter is None else identifiers(parameter)
    return {
        name
        for parameter in parameters.named_children
        for name in identifiers(parameter.child_by_field_name("pattern") or parameter)
    }


def references(node: Node, shadowed: frozenset[str] = frozenset()) -> set[str]:
    body = node.child_by_field_name("body")
    if body is None or node.type not in SCOPE_KINDS:
        return identifiers(node) - shadowed
    members = list(own_nodes(body))
    local = parameter_names(node) | {
        node_text(member.child_by_field_name("name")) or ""
        for member in members
        if member.type in {"variable_declarator", *SCOPE_KINDS}
    }
    masked = shadowed | local
    found = {
        node_text(member) or "" for member in members if member.type in {"identifier", "shorthand_property_identifier"}
    } - masked
    for member in members:
        if member.type in SCOPE_KINDS:
            found |= references(member, shadowed if node.type in {"class", "class_declaration"} else frozenset(masked))
    return found
