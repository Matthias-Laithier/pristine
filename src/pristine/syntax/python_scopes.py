from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.syntax.parsing import ParsedFile, all_nodes, node_text
from pristine.syntax.syntax_kinds import NESTED_SCOPE_KINDS

FUNCTION_KIND = "function_definition"
CLASS_KIND = "class_definition"
DECORATED_KIND = "decorated_definition"
ASSIGNMENT_KIND = "assignment"
RETURN_KIND = "return_statement"
SPLATS = frozenset({"list_splat_pattern", "dictionary_splat_pattern"})


def module_root(node: Node) -> Node:
    root = node
    while root.parent is not None:
        root = root.parent
    return root


def ancestors(node: Node) -> Iterator[Node]:
    ancestor = node.parent
    while ancestor is not None:
        yield ancestor
        ancestor = ancestor.parent


def enclosing_functions(node: Node) -> Iterator[Node]:
    return (ancestor for ancestor in ancestors(node) if ancestor.type == FUNCTION_KIND)


def enclosing_scope(node: Node) -> Node:
    ancestor = node.parent
    while ancestor is not None and ancestor.type not in NESTED_SCOPE_KINDS and ancestor.parent is not None:
        ancestor = ancestor.parent
    return node if ancestor is None else ancestor


def own_nodes(scope: Node, boundaries: frozenset[str] = NESTED_SCOPE_KINDS) -> Iterator[Node]:
    pending = list(reversed(scope.named_children))
    while pending:
        node = pending.pop()
        yield node
        if node.type not in boundaries:
            pending.extend(reversed(node.named_children))


def parameters(function: Node) -> dict[str, Node]:
    declared = function.child_by_field_name("parameters") if function.type == FUNCTION_KIND else None
    groups = [] if declared is None else declared.named_children
    names = ((next((node for node in all_nodes(group) if node.type == "identifier"), None), group) for group in groups)
    return {node_text(name) or "": group for name, group in names if name is not None}


def is_variadic(parameter: Node) -> bool:
    return parameter.type in SPLATS or any(child.type in SPLATS for child in parameter.named_children)


def named_parameters(function: Node) -> dict[str, Node]:
    return {name: group for name, group in parameters(function).items() if not is_variadic(group)}


def parameter_names(function: Node) -> list[str]:
    return list(named_parameters(function))


def all_parameter_names(source: Node | ParsedFile) -> list[str]:
    return [name for node in all_nodes(source) if node.type == FUNCTION_KIND for name in parameter_names(node)]


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


def defined_function(scope: Node, name: str | None) -> Node | None:
    definitions = (node for node in own_nodes(scope) if node.type == FUNCTION_KIND)
    return next((node for node in definitions if node_text(node.child_by_field_name("name")) == name), None)


def returned_values(definition: Node) -> list[Node | None]:
    returns = (node for node in own_nodes(definition) if node.type == RETURN_KIND)
    return [node.named_children[0] if node.named_children else None for node in returns]
