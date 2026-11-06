from functools import lru_cache

from tree_sitter import Node

from pristine.syntax.calls import callee_of
from pristine.syntax.parsing import all_nodes, node_text
from pristine.syntax.python_calls import import_bindings, qualified_callee
from pristine.syntax.python_scopes import defined_function, enclosing_scope, module_root, own_nodes

ASSIGNMENT_KINDS = frozenset({"assignment", "augmented_assignment"})
MUTATING_METHODS = frozenset({"append", "extend", "insert", "add", "update", "setdefault"})
BUILTIN_CONVERSIONS = frozenset({"int", "float", "len", "bool"})
ESCAPING_APIS = frozenset(
    {
        "shlex.quote",
        "html.escape",
        "markupsafe.escape",
        "markupsafe.Markup.escape",
        "psycopg.sql.Identifier",
        "psycopg.sql.Literal",
        "psycopg2.sql.Identifier",
        "psycopg2.sql.Literal",
        "psycopg2.extensions.quote_ident",
    }
)
IDENTIFIER_PREPARER = "identifier_preparer"
PREPARER_METHODS = frozenset({"quote", "quote_identifier", "quote_schema"})
SCOPE_CACHE_SIZE = 256


def assigned_values(scope: Node, name: str, before: Node) -> list[Node]:
    earlier = [node for node in scope_stores(scope).get(name, []) if node.end_byte < before.start_byte]
    assignments = (node.child_by_field_name("right") for node in earlier if node.type in ASSIGNMENT_KINDS)
    stored = [value for value in assignments if value is not None]
    added = [argument for node in earlier if node.type == "call" for argument in call_arguments(node)]
    return stored + added if stored else []


@lru_cache(maxsize=SCOPE_CACHE_SIZE)
def scope_stores(scope: Node) -> dict[str, list[Node]]:
    stores: dict[str, list[Node]] = {}
    for node in own_nodes(scope):
        name = stored_name(node) if node.type in ASSIGNMENT_KINDS else None
        name = mutated_name(node) if node.type == "call" else name
        if name is not None:
            stores.setdefault(name, []).append(node)
    return stores


def stored_name(assignment: Node) -> str | None:
    target = assignment.child_by_field_name("left")
    holder = target.child_by_field_name("value") if target is not None and target.type == "subscript" else target
    return node_text(holder) if holder is not None and holder.type == "identifier" else None


@lru_cache(maxsize=SCOPE_CACHE_SIZE)
def module_bindings(root: Node) -> dict[str, str]:
    return import_bindings(root)


def mutated_name(call: Node) -> str | None:
    function = call.child_by_field_name("function")
    if function is None or function.type != "attribute":
        return None
    receiver = function.child_by_field_name("object")
    is_mutator = node_text(function.child_by_field_name("attribute")) in MUTATING_METHODS
    return node_text(receiver) if is_mutator and receiver is not None and receiver.type == "identifier" else None


def call_arguments(call: Node) -> list[Node]:
    arguments = call.child_by_field_name("arguments")
    return [] if arguments is None else arguments.named_children


def is_escaping_api(call: Node) -> bool:
    callee = callee_of(call)
    if callee in BUILTIN_CONVERSIONS:
        return True
    if qualified_callee(callee, module_bindings(module_root(call))) in ESCAPING_APIS:
        return True
    function = call.child_by_field_name("function")
    receiver = None if function is None else function.child_by_field_name("object")
    is_preparer_method = (
        function is not None and node_text(function.child_by_field_name("attribute")) in PREPARER_METHODS
    )
    return is_preparer_method and receiver is not None and is_identifier_preparer(receiver)


def is_identifier_preparer(receiver: Node) -> bool:
    if receiver.type == "attribute":
        return node_text(receiver.child_by_field_name("attribute")) == IDENTIFIER_PREPARER
    if receiver.type != "identifier":
        return False
    values = assigned_values(enclosing_scope(receiver), node_text(receiver) or "", receiver)
    return bool(values) and all(map(is_identifier_preparer, values))


def local_helper(call: Node) -> Node | None:
    function = call.child_by_field_name("function")
    if function is None or function.type != "identifier":
        return None
    return defined_function(module_root(call), node_text(function))


def calls_local_helper(node: Node) -> bool:
    return any(child.type == "call" and local_helper(child) is not None for child in all_nodes(node))
