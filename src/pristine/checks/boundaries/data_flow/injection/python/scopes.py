from collections.abc import Iterator

from tree_sitter import Node

from pristine.syntax.calls import callee_of
from pristine.syntax.parsing import all_nodes, node_text
from pristine.syntax.python_calls import import_bindings, qualified_callee
from pristine.syntax.syntax_kinds import NESTED_SCOPE_KINDS

FUNCTION_KIND = "function_definition"
ASSIGNMENT_KINDS = frozenset({"assignment", "augmented_assignment"})
RETURN_KIND = "return_statement"
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


def enclosing_scope(node: Node) -> Node:
    ancestor = node.parent
    while ancestor is not None and ancestor.type not in NESTED_SCOPE_KINDS and ancestor.parent is not None:
        ancestor = ancestor.parent
    return node if ancestor is None else ancestor


def own_nodes(scope: Node) -> Iterator[Node]:
    return (node for node in all_nodes(scope) if node != scope and enclosing_scope(node) == scope)


def parameter_names(scope: Node) -> set[str]:
    parameters = scope.child_by_field_name("parameters") if scope.type == FUNCTION_KIND else None
    names = (node for node in all_nodes(parameters) if node.type == "identifier") if parameters else iter(())
    return {node_text(name) or "" for name in names}


def assigned_values(scope: Node, name: str, before: Node) -> list[Node]:
    earlier = [node for node in own_nodes(scope) if node.end_byte < before.start_byte]
    assignments = (node for node in earlier if node.type in ASSIGNMENT_KINDS)
    pairs = ((node.child_by_field_name("left"), node.child_by_field_name("right")) for node in assignments)
    stored = [
        value for target, value in pairs if value is not None and target is not None and stores_into(target, name)
    ]
    mutations = (node for node in earlier if node.type == "call" and mutated_name(node) == name)
    added = [argument for call in mutations for argument in call_arguments(call)]
    return stored + added if stored else []


def stores_into(target: Node, name: str) -> bool:
    holder = target.child_by_field_name("value") if target.type == "subscript" else target
    return holder is not None and holder.type == "identifier" and node_text(holder) == name


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


def module_root(node: Node) -> Node:
    root = node
    while root.parent is not None:
        root = root.parent
    return root


def is_escaping_api(call: Node) -> bool:
    callee = callee_of(call)
    if callee in BUILTIN_CONVERSIONS:
        return True
    if qualified_callee(callee, import_bindings(module_root(call))) in ESCAPING_APIS:
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
    name = node_text(function)
    root = module_root(call)
    definitions = (node for node in own_nodes(root) if node.type == FUNCTION_KIND)
    return next((node for node in definitions if node_text(node.child_by_field_name("name")) == name), None)


def returned_values(definition: Node) -> list[Node | None]:
    returns = (node for node in own_nodes(definition) if node.type == RETURN_KIND)
    return [node.named_children[0] if node.named_children else None for node in returns]


def calls_local_helper(node: Node) -> bool:
    return any(child.type == "call" and local_helper(child) is not None for child in all_nodes(node))
