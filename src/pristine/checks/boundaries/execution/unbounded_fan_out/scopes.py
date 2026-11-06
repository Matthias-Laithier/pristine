from collections.abc import Iterator

from tree_sitter import Node

from pristine.syntax.parsing import all_nodes, node_text
from pristine.syntax.syntax_kinds import NESTED_SCOPE_KINDS

FUNCTION_KIND = "function_definition"
CLASS_KIND = "class_definition"
ASSIGNMENT_KIND = "assignment"
DECORATED_KIND = "decorated_definition"
SPLATS = frozenset({"list_splat_pattern", "dictionary_splat_pattern"})


def enclosing_functions(node: Node) -> Iterator[Node]:
    ancestor = node.parent
    while ancestor is not None:
        if ancestor.type == FUNCTION_KIND:
            yield ancestor
        ancestor = ancestor.parent


def own_nodes(scope: Node) -> Iterator[Node]:
    pending = list(reversed(scope.named_children))
    while pending:
        node = pending.pop()
        yield node
        if node.type not in NESTED_SCOPE_KINDS:
            pending.extend(reversed(node.named_children))


def named_parameters(function: Node) -> dict[str, Node]:
    parameters = function.child_by_field_name("parameters")
    groups = [group for group in ([] if parameters is None else parameters.named_children) if not is_variadic(group)]
    names = ((next((node for node in all_nodes(group) if node.type == "identifier"), None), group) for group in groups)
    return {node_text(name) or "": group for name, group in names if name is not None}


def is_variadic(parameter: Node) -> bool:
    return parameter.type in SPLATS or any(child.type in SPLATS for child in parameter.named_children)


def parameter_names(function: Node) -> list[str]:
    return list(named_parameters(function))


def is_method(function: Node) -> bool:
    definition = function.parent if function.parent is not None and function.parent.type == DECORATED_KIND else function
    body = definition.parent
    return body is not None and body.parent is not None and body.parent.type == CLASS_KIND


def receiver_name(function: Node) -> str | None:
    names = parameter_names(function)
    return names[0] if names and is_method(function) else None


def assigned_values(scope: Node, target: str) -> list[Node]:
    assignments = (node for node in own_nodes(scope) if node.type == ASSIGNMENT_KIND)
    pairs = ((node.child_by_field_name("left"), node.child_by_field_name("right")) for node in assignments)
    return [value for left, value in pairs if value is not None and node_text(left) == target]


def module_root(node: Node) -> Node:
    root = node
    while root.parent is not None:
        root = root.parent
    return root
