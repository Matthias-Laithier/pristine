from collections import Counter

lazy from tree_sitter import Node

from pristine.checks.boundaries.execution.swallowed_failures.handlers import HandlerScope, callee_text, normalized
from pristine.syntax.parsing import ParsedFile, module_statements, node_text, root_of, typed_nodes

CONSOLE = "console"
CONSTANT_KEYWORD = "const"
BINDING_FIELDS = {
    "variable_declarator": "name",
    "required_parameter": "pattern",
    "optional_parameter": "pattern",
    "function_declaration": "name",
    "class_declaration": "name",
    "assignment_expression": "left",
}
BARE_BINDING_KINDS = frozenset({"formal_parameters", "import_clause", "namespace_import"})
SHORTHAND_PATTERN = "shorthand_property_identifier_pattern"
BINDING_KINDS = frozenset({"import_specifier", *BINDING_FIELDS, *BARE_BINDING_KINDS, SHORTHAND_PATTERN})


def binding_nodes(node: Node) -> list[Node | None]:
    if node.type == "import_specifier":
        return [node.child_by_field_name("alias") or node.child_by_field_name("name")]
    if node.type in BINDING_FIELDS:
        return [node.child_by_field_name(BINDING_FIELDS[node.type])]
    if node.type in BARE_BINDING_KINDS:
        return [child for child in node.named_children if child.type == "identifier"]
    return [node] if node.type == SHORTHAND_PATTERN else []


def bound_names(source: Node | ParsedFile) -> Counter[str]:
    bindings = (binding for node in typed_nodes(source, *BINDING_KINDS) for binding in binding_nodes(node))
    return Counter(node_text(binding) or "" for binding in bindings if binding is not None)


def logging_callees(source: Node | ParsedFile, names: Counter[str]) -> frozenset[str]:
    if names[CONSOLE]:
        return frozenset[str]()
    functions = (node.child_by_field_name("function") for node in typed_nodes(source, "call_expression"))
    receivers = (
        (function, function.child_by_field_name("object"))
        for function in functions
        if function is not None and function.type == "member_expression"
    )
    return frozenset(callee_text(function) for function, receiver in receivers if node_text(receiver) == CONSOLE)


def default_constants(source: Node | ParsedFile, names: Counter[str], default_values: frozenset[str]) -> frozenset[str]:
    declarations = (
        statement
        for statement in module_statements(root_of(source))
        if statement.type == "lexical_declaration" and statement.children[0].type == CONSTANT_KEYWORD
    )
    declarators = (declarator for declaration in declarations for declarator in declaration.named_children)
    pairs = (
        (declarator.child_by_field_name("name"), declarator.child_by_field_name("value")) for declarator in declarators
    )
    return frozenset(
        node_text(name) or ""
        for name, value in pairs
        if name is not None
        and name.type == "identifier"
        and value is not None
        and normalized(value) in default_values
        and names[node_text(name) or ""] == 1
    )


def script_scope(source: Node | ParsedFile, default_values: frozenset[str]) -> HandlerScope:
    names = bound_names(source)
    return HandlerScope(logging_callees(source, names), default_constants(source, names, default_values))
