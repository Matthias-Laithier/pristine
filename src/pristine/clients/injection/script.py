from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.clients.injection import RECEIVER, InjectedClient, called_injections, dotted_path
from pristine.clients.libraries import SCRIPT_ENTRY_POINTS
from pristine.clients.literals import string_content
from pristine.clients.script_imports import bound_name, import_bindings
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text, typed_nodes
from pristine.syntax.python_scopes import ancestors

PARAMETER_KINDS = frozenset({"required_parameter", "optional_parameter"})
PROPERTY_MODIFIERS = frozenset({"accessibility_modifier", "readonly", "override_modifier"})
CLASS_KINDS = frozenset({"class_declaration", "abstract_class_declaration", "class"})
TYPE_NAME_KINDS = frozenset({"type_identifier", "nested_type_identifier"})
WRAPPER_KINDS = frozenset({"type_annotation", "union_type"})
FIELD_KIND = "public_field_definition"
THIS = "this"


def binding_targets(binding: Node, source: str) -> Iterator[tuple[str, str]]:
    if binding.type == "named_imports":
        for specifier in binding.named_children:
            name = node_text(specifier.child_by_field_name("name")) or ""
            yield node_text(specifier.child_by_field_name("alias")) or name, f"{source}/{name}"
    elif binding.type == "namespace_import":
        yield bound_name(binding), source
    else:
        yield bound_name(binding), f"{source}/default"


def type_bindings(source: Node | ParsedFile) -> dict[str, str]:
    statements = typed_nodes(source, "import_statement")
    sources = ((statement, string_content(statement.child_by_field_name("source"))) for statement in statements)
    pairs = (
        binding_targets(binding, source)
        for statement, source in sources
        if source is not None
        for binding in import_bindings(statement)
    )
    return {local: target for targets in pairs for local, target in targets}


def type_names(annotation: Node) -> list[str]:
    if annotation.type in WRAPPER_KINDS:
        return [name for child in annotation.named_children for name in type_names(child)]
    return [node_text(annotation) or ""] if annotation.type in TYPE_NAME_KINDS else []


def qualified_type(name: str, bindings: dict[str, str]) -> str | None:
    head, _, rest = name.partition(".")
    base = bindings.get(head)
    return None if base is None else f"{base}/{rest}" if rest else base


def entry_point(annotation: Node | None, bindings: dict[str, str]) -> str | None:
    names = [] if annotation is None else type_names(annotation)
    qualified = (qualified_type(name, bindings) for name in names)
    return next((name for name in qualified if name in SCRIPT_ENTRY_POINTS), None)


def owning_class(node: Node) -> Node | None:
    return next((ancestor for ancestor in ancestors(node) if ancestor.type in CLASS_KINDS), None)


def parameter_injections(parameter: Node, client: str) -> Iterator[InjectedClient]:
    name = parameter.child_by_field_name("pattern")
    function = parameter.parent.parent if parameter.parent is not None else None
    if name is None or name.type != "identifier" or function is None:
        return
    yield InjectedClient(function, (node_text(name) or "",), client, line_of(parameter))
    owner = owning_class(function)
    if owner is not None and any(child.type in PROPERTY_MODIFIERS for child in parameter.children):
        yield InjectedClient(owner, (RECEIVER, node_text(name) or ""), client, line_of(parameter))


def field_injections(field: Node, client: str) -> Iterator[InjectedClient]:
    name = field.child_by_field_name("name")
    owner = owning_class(field)
    if owner is not None and name is not None and name.type == "property_identifier":
        yield InjectedClient(owner, (RECEIVER, node_text(name) or ""), client, line_of(field))


def script_injections(source: Node | ParsedFile) -> Iterator[InjectedClient]:
    bindings = type_bindings(source)
    for node in typed_nodes(source, *PARAMETER_KINDS, FIELD_KIND):
        client = entry_point(node.child_by_field_name("type"), bindings)
        if client is not None and node.type in PARAMETER_KINDS:
            yield from parameter_injections(node, client)
        elif client is not None and node.type == FIELD_KIND:
            yield from field_injections(node, client)


def callee_paths(scope: Node) -> set[tuple[str, ...]]:
    calls = (node for node in all_nodes(scope) if node.type == "call_expression")
    paths = (dotted_path(call.child_by_field_name("function")) for call in calls)
    return {(RECEIVER, *path[1:]) if path[0] == THIS else path for path in paths if path is not None}


def script_injected_clients(source: Node | ParsedFile) -> Iterator[tuple[str, int]]:
    return called_injections(script_injections(source), callee_paths)
