from collections.abc import Iterator
from functools import lru_cache

from tree_sitter import Node

from pristine.syntax.parsing import all_nodes, module_statements, node_text
from pristine.syntax.python_scopes import module_root

DEFAULT = "default"
NAMESPACE = "*"
REQUIRE = "require"
NUMBER_CONVERSIONS = frozenset({"Number", "parseInt", "parseFloat"})
ESCAPING_EXPORTS = frozenset(
    {
        ("dompurify", "sanitize"),
        ("isomorphic-dompurify", "sanitize"),
        ("sanitize-html", DEFAULT),
        ("escape-html", DEFAULT),
        ("lodash", "escape"),
        ("lodash-es", "escape"),
        ("lodash/escape", DEFAULT),
        ("he", "escape"),
        ("he", "encode"),
    }
)
DEFAULT_OBJECT_PACKAGES = frozenset({"dompurify", "isomorphic-dompurify", "lodash", "he"})
ROOT_CACHE_SIZE = 8


def string_text(node: Node | None) -> str | None:
    return None if node is None or node.type != "string" else (node_text(node) or "")[1:-1]


def clause_imports(clause: Node, source: str) -> Iterator[tuple[str, tuple[str, str]]]:
    for child in clause.named_children:
        if child.type == "identifier":
            yield node_text(child) or "", (source, DEFAULT)
        if child.type == "namespace_import" and child.named_children:
            yield node_text(child.named_children[0]) or "", (source, NAMESPACE)
        for specifier in child.named_children if child.type == "named_imports" else []:
            name = node_text(specifier.child_by_field_name("name")) or ""
            yield node_text(specifier.child_by_field_name("alias")) or name, (source, name)


def required_imports(declarator: Node) -> Iterator[tuple[str, tuple[str, str]]]:
    value = declarator.child_by_field_name("value")
    function = None if value is None or value.type != "call_expression" else value.child_by_field_name("function")
    arguments = None if value is None else value.child_by_field_name("arguments")
    source = string_text(arguments.named_children[0]) if arguments is not None and arguments.named_children else None
    pattern = declarator.child_by_field_name("name")
    if node_text(function) != REQUIRE or source is None or pattern is None:
        return
    if pattern.type == "identifier":
        yield node_text(pattern) or "", (source, DEFAULT)
    for child in pattern.named_children if pattern.type == "object_pattern" else []:
        local = child.child_by_field_name("value") or child
        yield node_text(local) or "", (source, node_text(child.child_by_field_name("key") or child) or "")


@lru_cache(maxsize=ROOT_CACHE_SIZE)
def script_imports(root: Node) -> dict[str, tuple[str, str]]:
    imports: dict[str, tuple[str, str]] = {}
    for statement in module_statements(root):
        clause = next((child for child in statement.named_children if child.type == "import_clause"), None)
        source = string_text(statement.child_by_field_name("source"))
        if statement.type == "import_statement" and clause is not None and source is not None:
            imports.update(clause_imports(clause, source))
        declarators = (node for node in all_nodes(statement) if node.type == "variable_declarator")
        imports.update(binding for declarator in declarators for binding in required_imports(declarator))
    return imports


def imported_export(function: Node, imports: dict[str, tuple[str, str]]) -> tuple[str, str] | None:
    if function.type == "identifier":
        return imports.get(node_text(function) or "")
    receiver = function.child_by_field_name("object")
    member = node_text(function.child_by_field_name("property")) or ""
    source, imported = imports.get(node_text(receiver) or "", ("", ""))
    is_object = imported == NAMESPACE or (imported == DEFAULT and source in DEFAULT_OBJECT_PACKAGES)
    return (source, member) if function.type == "member_expression" and is_object else None


def is_escaping_api(call: Node) -> bool:
    function = call.child_by_field_name("function")
    if function is None:
        return False
    if node_text(function) in NUMBER_CONVERSIONS:
        return True
    return imported_export(function, script_imports(module_root(call))) in ESCAPING_EXPORTS
