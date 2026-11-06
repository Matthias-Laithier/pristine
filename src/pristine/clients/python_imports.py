from collections import defaultdict
from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text

TYPE_CHECKING_CONDITIONS = frozenset({"TYPE_CHECKING", "typing.TYPE_CHECKING"})
PLAIN_IMPORT_KIND = "import_statement"
FROM_IMPORT_KIND = "import_from_statement"

RAISE_KIND = "raise_statement"

type AttributeUses = dict[str, set[str]]


def is_type_checking_only(node: Node) -> bool:
    ancestor = node.parent
    while ancestor is not None:
        condition = node_text(ancestor.child_by_field_name("condition"))
        if ancestor.type == "if_statement" and condition in TYPE_CHECKING_CONDITIONS:
            return True
        ancestor = ancestor.parent
    return False


def attribute_uses(source: Node | ParsedFile) -> AttributeUses:
    uses: AttributeUses = defaultdict(set)
    for node in all_nodes(source):
        owner = node_text(node.child_by_field_name("object")) if node.type == "attribute" else None
        if owner is not None:
            uses[owner].add(node_text(node.child_by_field_name("attribute")) or "")
    return uses


def imported_name(name: Node) -> str:
    return node_text(name.child_by_field_name("name") or name) or ""


def bound_name(name: Node) -> str:
    return node_text(name.child_by_field_name("alias")) or imported_name(name)


def qualified(module: str, name: str) -> str:
    return f"{module}.{name}" if name else module


def called_references(source: Node | ParsedFile) -> set[str]:
    calls = (
        node
        for node in all_nodes(source)
        if node.type == "call" and node.parent and node.parent.type != RAISE_KIND
    )
    callees = ("".join((node_text(call.child_by_field_name("function")) or "").split()) for call in calls)
    segments = (callee.split("(", 1)[0].split(".") for callee in callees)
    return {".".join(parts[:end]) for parts in segments for end in range(1, len(parts) + 1)}


def plain_import_targets(statement: Node, uses: AttributeUses, called: set[str]) -> Iterator[str]:
    for name in statement.children_by_field_name("name"):
        module, bound = imported_name(name), bound_name(name)
        attributes = uses.get(bound) or {""}
        yield from (qualified(module, attribute) for attribute in attributes if qualified(bound, attribute) in called)


def from_import_targets(statement: Node, called: set[str]) -> Iterator[str]:
    module = node_text(statement.child_by_field_name("module_name")) or ""
    names = [name for name in statement.children_by_field_name("name") if bound_name(name) in called]
    yield from (qualified(module, imported_name(name)) for name in names)


def statement_targets(statement: Node, uses: AttributeUses, called: set[str]) -> list[str]:
    if is_type_checking_only(statement):
        return []
    if statement.type == PLAIN_IMPORT_KIND:
        return list(plain_import_targets(statement, uses, called))
    if statement.type == FROM_IMPORT_KIND:
        return list(from_import_targets(statement, called))
    return []


def python_import_targets(source: Node | ParsedFile) -> Iterator[tuple[str, int]]:
    uses, called = attribute_uses(source), called_references(source)
    for statement in all_nodes(source):
        targets = statement_targets(statement, uses, called)
        yield from ((target, line_of(statement)) for target in targets)
