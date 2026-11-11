from collections.abc import Iterator
from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.checks.definitions import FileCheck
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text
from pristine.syntax.python_scopes import FUNCTION_KIND, named_parameters, own_nodes

RULE_ID = "CO-12"
RECEIVER_NAMES = frozenset({"self", "cls"})
TEST_FUNCTION_PREFIX = "test_"
PRIVATE_PREFIX = "_"
IN_PLACE_METHODS = frozenset(
    {
        "append",
        "extend",
        "insert",
        "pop",
        "remove",
        "clear",
        "update",
        "setdefault",
        "add",
        "discard",
        "sort",
        "reverse",
    }
)
MUTABLE_COLLECTIONS = frozenset(
    {"list", "dict", "set", "bytearray", "defaultdict", "OrderedDict", "deque"}
    | {"List", "Dict", "Set", "DefaultDict", "Deque", "MutableMapping", "MutableSequence", "MutableSet"}
)
OPTIONAL_WRAPPER = "Optional"
WRITE_KINDS = frozenset({"assignment", "augmented_assignment"})
BINDING_FIELDS = {
    "assignment": "left",
    "augmented_assignment": "left",
    "for_statement": "left",
    "for_in_clause": "left",
    "named_expression": "name",
    "as_pattern": "alias",
}
SCOPE_DECLARATIONS = frozenset({"global_statement", "nonlocal_statement"})
PATTERN_KINDS = frozenset(
    {"pattern_list", "tuple_pattern", "list_pattern", "list_splat_pattern", "as_pattern_target", "tuple", "list"}
    | {"parenthesized_expression"}
)
MESSAGE = (
    "function '{function}' mutates its parameter '{parameter}' in place; return a new value, "
    "or move the change into a method of the object that owns this state"
)


def subscript_root(target: Node) -> str | None:
    holder = target
    while holder.type == "subscript" and len(holder.children_by_field_name("subscript")) == 1:
        holder = holder.child_by_field_name("value") or holder
        if holder.type == "identifier":
            return node_text(holder)
    return None


def write_targets(node: Node) -> list[Node]:
    if node.type in WRITE_KINDS:
        target = node.child_by_field_name("left")
        return [] if target is None else [target, *target.named_children]
    if node.type == "delete_statement" and node.named_children:
        target = node.named_children[0]
        return [target, *target.named_children]
    return []


def called_receiver(node: Node) -> str | None:
    callee = node.child_by_field_name("function") if node.type == "call" else None
    if callee is None or callee.type != "attribute":
        return None
    receiver = callee.child_by_field_name("object")
    is_mutator = node_text(callee.child_by_field_name("attribute")) in IN_PLACE_METHODS
    return node_text(receiver) if is_mutator and receiver is not None and receiver.type == "identifier" else None


def mutated_name(node: Node, collections: set[str]) -> str | None:
    receiver = called_receiver(node)
    if receiver in collections:
        return receiver
    return next(filter(None, map(subscript_root, write_targets(node))), None)


def bound_names(node: Node) -> Iterator[str]:
    if node.type in SCOPE_DECLARATIONS:
        yield from (node_text(name) or "" for name in node.named_children)
    target = node.child_by_field_name(BINDING_FIELDS.get(node.type, ""))
    pending = [] if target is None else [target]
    while pending:
        current = pending.pop()
        if current.type == "identifier":
            yield node_text(current) or ""
        elif current.type in PATTERN_KINDS:
            pending.extend(current.named_children)


def type_name(annotation: Node) -> str | None:
    if annotation.type == "type" and annotation.named_children:
        return type_name(annotation.named_children[0])
    if annotation.type in {"generic_type", "subscript"} and annotation.named_children:
        outer = type_name(annotation.named_children[0])
        inner = annotation.named_children[-1] if outer == OPTIONAL_WRAPPER else None
        return outer if inner is None else type_name(inner)
    if annotation.type == "union_type":
        members = [type_name(member) for member in annotation.named_children]
        named = {member for member in members if member != "None"}
        return named.pop() if len(named) == 1 else None
    if annotation.type in {"identifier", "attribute", "none"}:
        return (node_text(annotation) or "").rsplit(".", 1)[-1]
    return None


def is_mutable_collection(parameter: Node) -> bool:
    annotation = parameter.child_by_field_name("type")
    return annotation is not None and type_name(annotation) in MUTABLE_COLLECTIONS


def first_mutations(definition: Node) -> dict[str, Node]:
    declared = {name: group for name, group in named_parameters(definition).items() if name not in RECEIVER_NAMES}
    collections = {name for name, group in declared.items() if is_mutable_collection(group)}
    body = list(own_nodes(definition))
    rebound = {name for node in body for name in bound_names(node)}
    mutations = ((mutated_name(node, collections), node) for node in reversed(body))
    return {name: node for name, node in mutations if name in declared and name not in rebound}


def is_called_name(name: Node) -> bool:
    holder = name.parent
    return holder is not None and holder.type == "call" and holder.child_by_field_name("function") == name


def callback_names(root: Node) -> set[str]:
    names = (node for node in all_nodes(root) if node.type == "identifier")
    return {
        node_text(name) or ""
        for name in names
        if name.parent is not None and name.parent.type != FUNCTION_KIND and not is_called_name(name)
    }


def is_exempt(function: str, callbacks: set[str]) -> bool:
    return function.startswith((TEST_FUNCTION_PREFIX, PRIVATE_PREFIX)) or function in callbacks


def mutation_findings(path: str, definition: Node, callbacks: set[str]) -> list[Finding]:
    function = node_text(definition.child_by_field_name("name")) or ""
    if definition.type != FUNCTION_KIND or is_exempt(function, callbacks):
        return []
    mutations = sorted(first_mutations(definition).items(), key=lambda item: item[1].start_byte)
    return [
        Finding(path, line_of(node), RULE_ID, Severity.WARNING, MESSAGE.format(function=function, parameter=name))
        for name, node in mutations
    ]


def check_parameter_mutation(parsed: ParsedFile) -> list[Finding]:
    if parsed.language != "python" or is_test_path(PurePath(parsed.path)):
        return []
    callbacks = callback_names(parsed.root)
    return [
        finding for node in parsed.root.named_children for finding in mutation_findings(parsed.path, node, callbacks)
    ]


CHECK = FileCheck(
    rule_id=RULE_ID,
    title="Localize Mutation",
    summary=(
        "Public, undecorated Python module-level functions outside tests, never passed as a callback in their module, "
        "that write or delete an item of one of their "
        "parameters, or call an in-place method on a parameter annotated as a builtin mutable collection, "
        "without rebinding it first."
    ),
    run=check_parameter_mutation,
)
