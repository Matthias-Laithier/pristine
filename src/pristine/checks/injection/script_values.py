from collections.abc import Callable

from tree_sitter import Node

from pristine.checks.injection.constructed import is_constant_reference, is_escaping_callee, is_placeholder_name
from pristine.parsing import module_statements, node_text
from pristine.registration import registering

LITERAL_KINDS = frozenset({"string", "number", "true", "false", "null", "undefined"})
COMPOSITE_KINDS = frozenset(
    {"parenthesized_expression", "binary_expression", "template_substitution", "template_string"}
)
BUILT_KINDS = frozenset({"template_string", "binary_expression"})
CONSTANT_KEYWORD = "const"
TEXT_KINDS = frozenset({"string_fragment", "escape_sequence"})

_TRUST_RULES: dict[str, Callable[[Node], bool]] = {}


def is_trusted(node: Node) -> bool:
    rule = _TRUST_RULES.get(node.type)
    return node.type in LITERAL_KINDS or (rule is not None and rule(node))


@registering(_TRUST_RULES, "identifier", "member_expression")
def is_constant_name(node: Node) -> bool:
    text = node_text(node) or ""
    return is_constant_reference(text) or is_placeholder_name(text) or text in module_literal_names(node)


def is_pure_literal(node: Node | None) -> bool:
    if node is None or node.type != "template_string":
        return node is not None and node.type in LITERAL_KINDS
    return all(child.type in TEXT_KINDS for child in node.named_children)


def module_literal_names(node: Node) -> set[str]:
    root = node
    while root.parent is not None:
        root = root.parent
    declarations = [
        statement
        for statement in module_statements(root)
        if statement.children and statement.children[0].type == CONSTANT_KEYWORD
    ]
    declarators = [declarator for declaration in declarations for declarator in declaration.named_children]
    literals = [declarator for declarator in declarators if is_pure_literal(declarator.child_by_field_name("value"))]
    return {node_text(declarator.child_by_field_name("name")) or "" for declarator in literals}


@registering(_TRUST_RULES, "call_expression")
def is_escaping_call(node: Node) -> bool:
    return is_escaping_callee(node_text(node.child_by_field_name("function")) or "")


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
