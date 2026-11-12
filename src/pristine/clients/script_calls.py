lazy from tree_sitter import Node

from pristine.clients.injection.script import binding_targets
from pristine.clients.literals import string_content
from pristine.clients.script_imports import import_bindings, is_type_only_import
from pristine.syntax.nodes import FUNCTION_KINDS
from pristine.syntax.parsing import ParsedFile, all_nodes, node_text

LEXICAL_SCOPES = frozenset(
    {"program", "statement_block", "catch_clause", "for_statement", "for_in_statement", "switch_body"}
)
BINDING_FIELDS = {
    "pair_pattern": "value",
    "assignment_pattern": "left",
    "required_parameter": "pattern",
    "optional_parameter": "pattern",
    "object_assignment_pattern": "left",
}
DECLARING_SCOPES = FUNCTION_KINDS | LEXICAL_SCOPES
LOCAL_BOUNDARIES = FUNCTION_KINDS | {"class_declaration", "class"}
PATTERN_CONTAINERS = frozenset({"object_pattern", "array_pattern", "rest_pattern", "formal_parameters"})
BOUND_IDENTIFIERS = frozenset({"identifier", "shorthand_property_identifier_pattern"})


def runtime_binding_targets(binding: Node, source: str) -> dict[str, str]:
    if binding.type != "named_imports":
        return dict(binding_targets(binding, source))
    targets = {}
    for specifier in binding.named_children:
        if is_type_only_import(specifier):
            continue
        name = node_text(specifier.child_by_field_name("name")) or ""
        local = node_text(specifier.child_by_field_name("alias")) or name
        targets[local] = f"{source}/{name}"
    return targets


def script_bindings(parsed: ParsedFile) -> dict[str, str]:
    targets = {}
    for statement in all_nodes(parsed):
        source = string_content(statement.child_by_field_name("source"))
        if statement.type != "import_statement" or source is None or is_type_only_import(statement):
            continue
        for binding in import_bindings(statement):
            targets.update(runtime_binding_targets(binding, source))
    return targets


def enclosing_function(node: Node) -> Node | None:
    scope = node.parent
    while scope is not None and scope.type not in FUNCTION_KINDS:
        scope = scope.parent
    return scope


def bound_names(pattern: Node | None) -> set[str]:
    if pattern is None:
        return set()
    if pattern.type in BOUND_IDENTIFIERS:
        return {node_text(pattern) or ""}
    if pattern.type in BINDING_FIELDS:
        return bound_names(pattern.child_by_field_name(BINDING_FIELDS[pattern.type]))
    if pattern.type not in PATTERN_CONTAINERS:
        return set()
    return {name for child in pattern.named_children for name in bound_names(child)}


def local_nodes(scope: Node, *, include_blocks: bool = False) -> list[Node]:
    pending = list(scope.named_children)
    nodes = []
    while pending:
        node = pending.pop()
        nodes.append(node)
        boundary = node.type in LOCAL_BOUNDARIES or (not include_blocks and node.type in LEXICAL_SCOPES)
        if not boundary:
            pending.extend(node.named_children)
    return nodes


def imported_names(statement: Node) -> set[str]:
    if is_type_only_import(statement):
        return set()
    return {name for binding in import_bindings(statement) for name in runtime_binding_targets(binding, "")}


def declaration_names(node: Node, *, include_imports: bool) -> set[str]:
    fields = {
        "variable_declarator": "name",
        "assignment_expression": "left",
        "function_declaration": "name",
        "class_declaration": "name",
    }
    if node.type == "import_statement":
        return imported_names(node) if include_imports else set()
    return bound_names(node.child_by_field_name(fields.get(node.type, "")))


def scope_names(scope: Node, *, include_imports: bool) -> frozenset[str]:
    fields = {"catch_clause": "parameter", "for_in_statement": "left"}
    parameter = scope.child_by_field_name(fields.get(scope.type, ""))
    if scope.type in FUNCTION_KINDS:
        parameter = scope.child_by_field_name("parameters") or scope.child_by_field_name("parameter")
    names = bound_names(parameter)
    for node in local_nodes(scope):
        names |= declaration_names(node, include_imports=include_imports)
    if scope.type in FUNCTION_KINDS | {"program"}:
        for node in local_nodes(scope, include_blocks=True):
            names |= function_var_names(node)
    return frozenset(names)


def function_var_names(node: Node) -> set[str]:
    if node.type == "for_in_statement" and node_text(node.child_by_field_name("kind")) == "var":
        return bound_names(node.child_by_field_name("left"))
    if node.type == "variable_declarator" and node.parent is not None and node.parent.type == "variable_declaration":
        return bound_names(node.child_by_field_name("name"))
    return set()


class ScriptScopes:
    def __init__(self) -> None:
        self.names: dict[tuple[Node, bool], frozenset[str]] = {}

    def declared(self, scope: Node, *, include_imports: bool) -> frozenset[str]:
        key = scope, include_imports
        if key not in self.names:
            self.names[key] = scope_names(scope, include_imports=include_imports)
        return self.names[key]

    def is_shadowed(self, node: Node, name: str, *, include_imports: bool = True) -> bool:
        scope = node.parent
        while scope is not None:
            if scope.type in DECLARING_SCOPES and name in self.declared(scope, include_imports=include_imports):
                return True
            scope = scope.parent
        return False


def qualified_script_call(call: Node, bindings: dict[str, str], scopes: ScriptScopes) -> str | None:
    callee = node_text(call.child_by_field_name("function")) or ""
    head, _, tail = callee.partition(".")
    target = bindings.get(head)
    if target is None or scopes.is_shadowed(call, head, include_imports=False):
        return None
    return target + ("/" + tail.replace(".", "/") if tail else "")
