from collections.abc import Iterator
from dataclasses import dataclass

lazy from tree_sitter import Node

from pristine.clients.literals import string_content
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text, typed_nodes

SCRIPT_LOADER_NAMES = frozenset({"require", "import"})
CALLING_KINDS = {"call_expression": "function", "new_expression": "constructor"}
THROW_KIND = "throw_statement"
DECLARATOR_KIND = "variable_declarator"
BINDING_KINDS = frozenset({"identifier", "shorthand_property_identifier_pattern"})


@dataclass(frozen=True)
class CalledReferences:
    callees: set[str]
    receivers: set[str]

    def calls_export(self, name: str) -> bool:
        return name in self.callees

    def calls_into_module(self, name: str) -> bool:
        return name in self.receivers


def called_references(source: Node | ParsedFile) -> CalledReferences:
    calls = typed_nodes(source, *CALLING_KINDS)
    callees = {
        "".join((node_text(call.child_by_field_name(CALLING_KINDS[call.type])) or "").split())
        for call in calls
        if call.parent is None or call.parent.type != THROW_KIND
    }
    segments = (callee.split("(", 1)[0].split(".") for callee in callees)
    receivers = {".".join(parts[:end]) for parts in segments for end in range(1, len(parts) + 1)}
    return CalledReferences(callees, receivers)


def is_type_only_import(statement: Node) -> bool:
    return any(child.type == "type" for child in statement.children)


def import_bindings(statement: Node) -> list[Node]:
    clause = next((child for child in statement.named_children if child.type == "import_clause"), None)
    return [] if clause is None else clause.named_children


def bound_name(binding: Node) -> str:
    if binding.type == "namespace_import":
        return node_text(next(iter(binding.named_children), None)) or ""
    return node_text(binding) or ""


def named_import_targets(source: str, named_imports: Node, called: CalledReferences) -> Iterator[str]:
    for specifier in named_imports.named_children:
        local = specifier.child_by_field_name("alias") or specifier.child_by_field_name("name")
        if not is_type_only_import(specifier) and called.calls_export(node_text(local) or ""):
            yield f"{source}/{node_text(specifier.child_by_field_name('name'))}"


def script_import_targets(statement: Node, called: CalledReferences) -> Iterator[str]:
    source = string_content(statement.child_by_field_name("source"))
    if source is None or is_type_only_import(statement):
        return
    for binding in import_bindings(statement):
        if binding.type == "named_imports":
            yield from named_import_targets(source, binding, called)
        elif called.calls_into_module(bound_name(binding)):
            yield source


def is_used_load(call: Node, called: CalledReferences) -> bool:
    declarator = call.parent
    target = declarator.child_by_field_name("name") if declarator and declarator.type == DECLARATOR_KIND else None
    if target is None or target.type == "identifier":
        return target is not None and called.calls_into_module(node_text(target) or "")
    names = (node_text(node) or "" for node in all_nodes(target) if node.type in BINDING_KINDS)
    return any(map(called.calls_export, names))


def script_loader_targets(call: Node, called: CalledReferences) -> list[str]:
    loader = node_text(call.child_by_field_name("function"))
    arguments = call.child_by_field_name("arguments")
    if loader not in SCRIPT_LOADER_NAMES or arguments is None or arguments.named_child_count != 1:
        return []
    source = string_content(arguments.named_children[0])
    return [] if source is None or not is_used_load(call, called) else [source]


def script_import_modules(source: Node | ParsedFile) -> Iterator[tuple[str, int]]:
    called = called_references(source)
    for node in typed_nodes(source, "import_statement", "call_expression"):
        targets = list(script_import_targets(node, called)) if node.type == "import_statement" else []
        targets += script_loader_targets(node, called) if node.type == "call_expression" else []
        yield from ((target, line_of(node)) for target in targets)
