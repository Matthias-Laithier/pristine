from collections.abc import Callable, Iterator

from tree_sitter import Node

from pristine.checks.boundaries.execution.unbounded_fan_out.sizes import passes_size
from pristine.registration import registering
from pristine.syntax.calls import callee_of
from pristine.syntax.parsing import all_nodes, node_text
from pristine.syntax.python_calls import import_bindings, qualified_callee
from pristine.syntax.python_scopes import (
    assigned_values,
    enclosing_functions,
    module_root,
    parameter_names,
    receiver_name,
)
from pristine.syntax.syntax_kinds import COMPREHENSION_KINDS

TRANSPARENT_WRAPPERS = frozenset({"enumerate", "sorted", "reversed", "list", "tuple", "set"})
LOOP_CLAUSE_KINDS = frozenset({"for_statement", "for_in_clause"})
MAPPING_VIEWS = frozenset({"items", "keys", "values"})
GATHER = "asyncio.gather"

_DATA_RULES: dict[str, Callable[[Node], bool]] = {}


def collection_of(iterable: Node) -> Node:
    if iterable.type != "call" or callee_of(iterable) not in TRANSPARENT_WRAPPERS:
        return iterable
    arguments = iterable.child_by_field_name("arguments")
    inner = None if arguments is None or not arguments.named_children else arguments.named_children[0]
    return iterable if inner is None else collection_of(inner)


def loop_iterables(loop: Node) -> list[Node]:
    if loop.type == "call":
        arguments = loop.child_by_field_name("arguments")
        return [] if arguments is None else arguments.named_children[1:]
    clauses = [loop] if loop.type == "for_statement" else loop.named_children
    found = (clause.child_by_field_name("right") for clause in clauses if clause.type in LOOP_CLAUSE_KINDS)
    return [iterable for iterable in found if iterable is not None]


def loop_variables(loop: Node) -> set[str]:
    clauses = [loop] if loop.type == "for_statement" else loop.named_children
    targets = (clause.child_by_field_name("left") for clause in clauses if clause.type in LOOP_CLAUSE_KINDS)
    return {node_text(name) or "" for target in targets if target is not None for name in identifiers(target)}


def identifiers(node: Node) -> Iterator[Node]:
    return (child for child in all_nodes(node) if child.type == "identifier")


def is_data(node: Node | None) -> bool:
    rule = None if node is None else _DATA_RULES.get(collection_of(node).type)
    return node is not None and rule is not None and rule(collection_of(node))


@registering(_DATA_RULES, "await")
def is_awaited_load(node: Node) -> bool:
    awaited = node.named_children[0] if node.named_children else None
    if awaited is None or awaited.type != "call":
        return True
    if qualified_callee(callee_of(awaited), import_bindings(module_root(node))) == GATHER:
        return is_gathered_data(awaited)
    return not passes_size(awaited)


def is_gathered_data(gather: Node) -> bool:
    arguments = gather.child_by_field_name("arguments")
    spreads = [] if arguments is None else [node for node in arguments.named_children if node.type == "list_splat"]
    loops = (spread.named_children[0] for spread in spreads if spread.named_children)
    return any(is_data(iterable) for loop in loops for iterable in loop_iterables(loop))


@registering(_DATA_RULES, "call")
def is_mapping_view(node: Node) -> bool:
    function = node.child_by_field_name("function")
    if function is None or function.type != "attribute":
        return False
    return node_text(function.child_by_field_name("attribute")) in MAPPING_VIEWS and is_data(
        function.child_by_field_name("object")
    )


@registering(_DATA_RULES, "attribute")
def is_data_attribute(node: Node) -> bool:
    return is_data(node.child_by_field_name("object"))


@registering(_DATA_RULES, "subscript")
def is_data_lookup(node: Node) -> bool:
    is_slice = any(child.type == "slice" for child in node.children_by_field_name("subscript"))
    return not is_slice and is_data(node.child_by_field_name("value"))


@registering(_DATA_RULES, *COMPREHENSION_KINDS)
def is_derived_collection(node: Node) -> bool:
    clauses = (clause for clause in node.named_children if clause.type == "for_in_clause")
    return any(is_data(clause.child_by_field_name("right")) for clause in clauses)


@registering(_DATA_RULES, "identifier")
def is_data_name(node: Node) -> bool:
    name = node_text(node) or ""
    for function in enclosing_functions(node):
        if name in parameter_names(function):
            return name != receiver_name(function)
        earlier = [value for value in assigned_values(function, name) if value.end_byte < node.start_byte]
        if earlier:
            return any(map(is_data, earlier))
    return False


def unbounded_collection(loop: Node) -> Node | None:
    return next((iterable for iterable in loop_iterables(loop) if is_data(iterable)), None)
