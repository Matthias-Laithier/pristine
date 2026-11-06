from collections.abc import Callable
from functools import lru_cache

from tree_sitter import Node

from pristine.checks.boundaries.data_flow.injection.constructed import is_constant_reference
from pristine.checks.boundaries.data_flow.injection.scripts.escaping import is_escaping_api
from pristine.registration import registering
from pristine.syntax.parsing import module_statements, node_text
from pristine.syntax.python_scopes import module_root

LITERAL_KINDS = frozenset({"string", "number", "true", "false", "null", "undefined"})
COMPOSITE_KINDS = frozenset(
    {"parenthesized_expression", "binary_expression", "template_substitution", "template_string"}
)
BUILT_KINDS = frozenset({"template_string", "binary_expression"})
CONSTANT_KEYWORD = "const"
DECLARATION_KIND = "lexical_declaration"
JOIN_METHOD = "join"
FILL_METHOD = "fill"
MAP_METHOD = "map"
TEXT_KINDS = frozenset({"string_fragment", "escape_sequence"})
ROOT_CACHE_SIZE = 8

_TRUST_RULES: dict[str, Callable[[Node], bool]] = {}


def is_trusted(node: Node) -> bool:
    rule = _TRUST_RULES.get(node.type)
    return node.type in LITERAL_KINDS or (rule is not None and rule(node))


@registering(_TRUST_RULES, "identifier", "member_expression")
def is_constant_name(node: Node) -> bool:
    text = node_text(node) or ""
    return is_constant_reference(text) or text in module_literal_names(module_root(node)) or is_trusted_constant(node)


def is_trusted_constant(node: Node) -> bool:
    values = constant_values(node) if node.type == "identifier" else []
    return bool(values) and all(map(is_trusted, values))


def constant_values(node: Node) -> list[Node]:
    scope = node.parent
    while scope is not None:
        values = declared_values(scope, node)
        if values:
            return values
        scope = scope.parent
    return []


def declared_values(scope: Node, use: Node) -> list[Node]:
    declarations = (
        statement
        for statement in scope.named_children
        if statement.type == DECLARATION_KIND
        and statement.children[0].type == CONSTANT_KEYWORD
        and statement.end_byte < use.start_byte
    )
    declarators = [declarator for declaration in declarations for declarator in declaration.named_children]
    values = (
        declarator.child_by_field_name("value")
        for declarator in declarators
        if node_text(declarator.child_by_field_name("name")) == node_text(use)
    )
    return [value for value in values if value is not None]


def is_pure_literal(node: Node | None) -> bool:
    if node is None or node.type != "template_string":
        return node is not None and node.type in LITERAL_KINDS
    return all(child.type in TEXT_KINDS for child in node.named_children)


@lru_cache(maxsize=ROOT_CACHE_SIZE)
def module_literal_names(root: Node) -> frozenset[str]:
    declarations = [
        statement
        for statement in module_statements(root)
        if statement.children and statement.children[0].type == CONSTANT_KEYWORD
    ]
    declarators = [declarator for declaration in declarations for declarator in declaration.named_children]
    literals = [declarator for declarator in declarators if is_pure_literal(declarator.child_by_field_name("value"))]
    return frozenset(node_text(declarator.child_by_field_name("name")) or "" for declarator in literals)


@registering(_TRUST_RULES, "call_expression")
def is_escaping_call(node: Node) -> bool:
    return is_escaping_api(node) or is_literal_join(node)


@registering(_TRUST_RULES, "array")
def is_literal_array(node: Node) -> bool:
    return all(map(is_trusted, node.named_children))


def call_parts(node: Node) -> tuple[Node | None, str | None, list[Node]]:
    function = node.child_by_field_name("function")
    arguments = node.child_by_field_name("arguments")
    listed = [] if arguments is None else arguments.named_children
    if function is None or function.type != "member_expression":
        return None, None, listed
    return function.child_by_field_name("object"), node_text(function.child_by_field_name("property")), listed


def is_literal_join(node: Node) -> bool:
    receiver, method, arguments = call_parts(node)
    return (
        method == JOIN_METHOD
        and receiver is not None
        and is_literal_sequence(receiver)
        and all(map(is_trusted, arguments))
    )


def is_literal_sequence(node: Node) -> bool:
    if node.type == "array":
        return is_trusted(node)
    _, method, arguments = call_parts(node) if node.type == "call_expression" else (None, None, [])
    if method == FILL_METHOD:
        return all(map(is_trusted, arguments))
    bodies = [argument.child_by_field_name("body") for argument in arguments if argument.type == "arrow_function"]
    return method == MAP_METHOD and len(bodies) == 1 and bodies[0] is not None and is_trusted(bodies[0])


@registering(_TRUST_RULES, *COMPOSITE_KINDS)
def is_literal_composite(node: Node) -> bool:
    parts = [child for child in node.named_children if child.type not in TEXT_KINDS]
    return all(map(is_trusted, parts))


def is_built(node: Node) -> bool:
    return node.type in BUILT_KINDS and not is_trusted(node)


def string_value(node: Node | None) -> str | None:
    if node is None or node.type != "string":
        return None
    return (node_text(node) or "")[1:-1]
