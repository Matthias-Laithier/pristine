from collections.abc import Iterator
from dataclasses import dataclass

lazy from tree_sitter import Node

from pristine.syntax.calls import callee_of
from pristine.syntax.parsing import ParsedFile, all_nodes, is_async, node_text
from pristine.syntax.python_calls import keyword_values, positional_arguments, qualified_callee
from pristine.syntax.python_scopes import (
    ASSIGNMENT_KIND,
    CLASS_KIND,
    FUNCTION_KIND,
    enclosing_functions,
    module_root,
    parameter_names,
    receiver_name,
)

LIMITER_FACTORIES = frozenset(
    {"asyncio.Semaphore", "asyncio.BoundedSemaphore", "asyncio.Queue", "anyio.Semaphore", "anyio.CapacityLimiter"}
)
ACQUIRING_METHODS = frozenset({"acquire", "get"})
RECEIVER_SEPARATOR = "."


@dataclass(frozen=True)
class Limiters:
    named: frozenset[tuple[int, str]]
    attributes: frozenset[str]
    bindings: dict[str, str]


def limiters_of(source: Node | ParsedFile, bindings: dict[str, str]) -> Limiters:
    root = source.root if isinstance(source, ParsedFile) else source
    named: set[tuple[int, str]] = set()
    attributes: set[str] = set()
    for assignment in (node for node in all_nodes(source) if node.type == ASSIGNMENT_KIND):
        target = assignment.child_by_field_name("left")
        value = assignment.child_by_field_name("right")
        if target is None or value is None or not creates_limiter(value, bindings):
            continue
        scope = next(enclosing_functions(assignment), None)
        is_class_field = target.type == "identifier" and scope_kind(assignment) == CLASS_KIND
        if target.type == "attribute" or is_class_field:
            attributes.add(last_segment(target))
        else:
            named.add((root.id if scope is None else scope.id, node_text(target) or ""))
    return Limiters(frozenset(named), frozenset(attributes), bindings)


def last_segment(node: Node) -> str:
    return (node_text(node) or "").rsplit(RECEIVER_SEPARATOR, 1)[-1]


def scope_kind(node: Node) -> str | None:
    ancestor = node.parent
    while ancestor is not None and ancestor.type not in {FUNCTION_KIND, CLASS_KIND}:
        ancestor = ancestor.parent
    return None if ancestor is None else ancestor.type


def creates_limiter(value: Node, bindings: dict[str, str]) -> bool:
    return value.type == "call" and qualified_callee(callee_of(value), bindings) in LIMITER_FACTORIES


def is_limiter(reference: Node, limiters: Limiters) -> bool:
    if reference.type == "attribute":
        return last_segment(reference) in limiters.attributes
    scopes = [*enclosing_functions(reference), module_root(reference)]
    text = node_text(reference) or ""
    return reference.type == "identifier" and any((scope.id, text) in limiters.named for scope in scopes)


def held_references(body: Node) -> Iterator[Node]:
    for node in all_nodes(body):
        held = entered_values(node) if node.type == "with_statement" and is_async(node) else [acquired_value(node)]
        yield from (reference for reference in held if reference is not None)


def entered_values(statement: Node) -> list[Node | None]:
    items = (item for item in all_nodes(statement) if item.type == "with_item")
    values = [item.child_by_field_name("value") for item in items]
    return [value.named_children[0] if value.type == "as_pattern" else value for value in values if value]


def acquired_value(node: Node) -> Node | None:
    awaited = node.named_children[0] if node.type == "await" and node.named_children else None
    function = None if awaited is None or awaited.type != "call" else awaited.child_by_field_name("function")
    if function is None or function.type != "attribute" or last_segment(function) not in ACQUIRING_METHODS:
        return None
    return function.child_by_field_name("object")


def passed_argument(definition: Node, call: Node | None, name: str) -> Node | None:
    arguments_node = None if call is None else call.child_by_field_name("arguments")
    if arguments_node is None:
        return None
    arguments = arguments_node.named_children
    parameters = [parameter for parameter in parameter_names(definition) if parameter != receiver_name(definition)]
    positional = positional_arguments(arguments)
    index = parameters.index(name) if name in parameters else len(positional)
    return positional[index] if index < len(positional) else keyword_values(arguments).get(name)


def acquires_limiter(definition: Node, call: Node | None, limiters: Limiters) -> bool:
    body = definition.child_by_field_name("body")
    for reference in [] if body is None else held_references(body):
        name = node_text(reference) or ""
        passed = passed_argument(definition, call, name) if name in parameter_names(definition) else None
        if is_limiter(reference, limiters) or (passed is not None and is_limiter(passed, limiters)):
            return True
    return False


def holds_limiter(body: Node, limiters: Limiters) -> bool:
    return any(is_limiter(reference, limiters) for reference in held_references(body))
