from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.checks.testing.model_clients_in_tests.live_clients import LiveClient, all_environment_reads, is_within
from pristine.clients.libraries import SCRIPT_MODEL_CLIENTS
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text, typed_nodes

API_KEY_PROPERTY = "apiKey"
ENVIRONMENTS = ("process.env", "import.meta.env")
CONSTRUCTING_KINDS = {"new_expression": "constructor", "call_expression": "function"}


def is_model_import(statement: Node) -> bool:
    source = (node_text(statement.child_by_field_name("source")) or "").strip("\"'`")
    is_type_only = any(child.type == "type" for child in statement.children)
    return statement.type == "import_statement" and not is_type_only and is_within(source, SCRIPT_MODEL_CLIENTS, "/")


def model_bindings(source: Node | ParsedFile) -> set[str]:
    clauses = (
        child
        for statement in typed_nodes(source, "import_statement")
        if is_model_import(statement)
        for child in statement.named_children
        if child.type == "import_clause"
    )
    return {name for clause in clauses for name in imported_names(clause)}


def imported_names(clause: Node) -> set[str]:
    specifiers = (node for node in all_nodes(clause) if node.type == "import_specifier")
    locals_ = {
        node_text(node.child_by_field_name("alias") or node.child_by_field_name("name")) or "" for node in specifiers
    }
    bare = (
        node
        for node in all_nodes(clause)
        if node.type == "identifier" and node.parent and node.parent.type != "import_specifier"
    )
    return locals_ | {node_text(node) or "" for node in bare}


def declared_values(source: Node | ParsedFile) -> dict[str, list[Node]]:
    values: dict[str, list[Node]] = {}
    for declarator in typed_nodes(source, "variable_declarator"):
        value = declarator.child_by_field_name("value")
        if value is not None:
            values.setdefault(node_text(declarator.child_by_field_name("name")) or "", []).append(value)
    return values


def environment_key(value: Node, declared: dict[str, list[Node]]) -> tuple[bool, str | None]:
    if value.type in {"identifier", "shorthand_property_identifier"}:
        reads = [environment_key(source, {}) for source in declared.get(node_text(value) or "", [])]
        return all_environment_reads(reads)
    container = (
        value.child_by_field_name("object") if value.type in {"member_expression", "subscript_expression"} else None
    )
    if container is None or "".join((node_text(container) or "").split()) not in ENVIRONMENTS:
        return False, None
    key = value.child_by_field_name("property") or value.child_by_field_name("index")
    return True, (node_text(key) or "").strip("\"'`") or None


def api_key_value(call: Node) -> Node | None:
    arguments = call.child_by_field_name("arguments")
    options = next(iter(arguments.named_children), None) if arguments is not None else None
    for entry in [] if options is None or options.type != "object" else options.named_children:
        if entry.type == "shorthand_property_identifier" and node_text(entry) == API_KEY_PROPERTY:
            return entry
        if entry.type == "pair" and node_text(entry.child_by_field_name("key")) == API_KEY_PROPERTY:
            return entry.child_by_field_name("value")
    return None


def script_live_clients(source: Node | ParsedFile) -> Iterator[LiveClient]:
    clients, declared = model_bindings(source), declared_values(source)
    calls = typed_nodes(source, *CONSTRUCTING_KINDS)
    for call in calls:
        callee = node_text(call.child_by_field_name(CONSTRUCTING_KINDS[call.type])) or ""
        key = api_key_value(call) if callee.split(".")[0] in clients else None
        is_read, name = (False, None) if key is None else environment_key(key, declared)
        if is_read:
            yield LiveClient(line_of(call), name)
