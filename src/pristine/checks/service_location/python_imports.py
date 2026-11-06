from collections import defaultdict
from collections.abc import Iterator

from tree_sitter import Node

from pristine.syntax.parsing import all_nodes, line_of, node_text

TYPE_CHECKING_CONDITIONS = frozenset({"TYPE_CHECKING", "typing.TYPE_CHECKING"})
PLAIN_IMPORT_KIND = "import_statement"
FROM_IMPORT_KIND = "import_from_statement"

type AttributeUses = dict[str, set[str]]


def is_type_checking_only(node: Node) -> bool:
    ancestor = node.parent
    while ancestor is not None:
        condition = node_text(ancestor.child_by_field_name("condition"))
        if ancestor.type == "if_statement" and condition in TYPE_CHECKING_CONDITIONS:
            return True
        ancestor = ancestor.parent
    return False


def attribute_uses(root: Node) -> AttributeUses:
    uses: AttributeUses = defaultdict(set)
    for node in all_nodes(root):
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


def plain_import_targets(statement: Node, uses: AttributeUses) -> Iterator[str]:
    for name in statement.children_by_field_name("name"):
        module = imported_name(name)
        attributes = uses.get(bound_name(name)) or {""}
        yield from (qualified(module, attribute) for attribute in attributes)


def from_import_targets(statement: Node) -> Iterator[str]:
    module = node_text(statement.child_by_field_name("module_name")) or ""
    names = [imported_name(name) for name in statement.children_by_field_name("name")]
    yield from (qualified(module, name) for name in names or [""])


def statement_targets(statement: Node, uses: AttributeUses) -> list[str]:
    if is_type_checking_only(statement):
        return []
    if statement.type == PLAIN_IMPORT_KIND:
        return list(plain_import_targets(statement, uses))
    if statement.type == FROM_IMPORT_KIND:
        return list(from_import_targets(statement))
    return []


def python_import_targets(root: Node) -> Iterator[tuple[str, int]]:
    uses = attribute_uses(root)
    for statement in all_nodes(root):
        targets = statement_targets(statement, uses)
        yield from ((target, line_of(statement)) for target in targets)
