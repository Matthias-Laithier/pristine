from collections.abc import Callable
from dataclasses import dataclass

from tree_sitter import Node

from pristine.checks.global_mutation.module_globals import PYTHON_COLLECTION, REBINDABLE, Globals
from pristine.parsing import node_text
from pristine.registration import registering
from pristine.syntax_kinds import CALL_KINDS

PYTHON_METHODS = frozenset({"append", "extend", "insert", "add", "update", "setdefault", "pop", "popitem"})
JS_ARRAY_METHODS = frozenset({"push", "pop", "shift", "unshift", "splice", "sort", "reverse", "fill", "copyWithin"})
METHODS_BY_KIND = {
    PYTHON_COLLECTION: PYTHON_METHODS | {"clear", "remove", "discard"},
    "array": JS_ARRAY_METHODS,
    "collection": frozenset({"set", "delete", "clear", "add"}),
}
ITEM_KINDS = frozenset({"subscript", "subscript_expression", "member_expression"})
METHOD_CALLEE_KINDS = frozenset({"attribute", "member_expression"})


@dataclass(frozen=True)
class Mutation:
    node: Node
    name: str
    action: str


type MutationFinder = Callable[[Node, Globals], Mutation | None]
_FINDERS: dict[str, MutationFinder] = {}


def kinds_of(globals_kinds: Globals, node: Node | None) -> frozenset[str]:
    name = node_text(node) if node is not None and node.type == "identifier" else None
    return globals_kinds.get(name or "", frozenset[str]())


def item_root(node: Node | None) -> Node | None:
    while node is not None and node.type in ITEM_KINDS:
        node = node.child_by_field_name("value") or node.child_by_field_name("object")
    return node


def written_target(node: Node, target: Node | None, globals_kinds: Globals) -> Mutation | None:
    if REBINDABLE in kinds_of(globals_kinds, target):
        return Mutation(node, node_text(target) or "", "reassigns")
    root = item_root(target)
    is_item = target is not None and target.type in ITEM_KINDS
    if is_item and kinds_of(globals_kinds, root) - {REBINDABLE}:
        return Mutation(node, node_text(root) or "", "changes an item of")
    return None


@registering(_FINDERS, "assignment", "augmented_assignment", "assignment_expression", "augmented_assignment_expression")
def assigned(node: Node, globals_kinds: Globals) -> Mutation | None:
    return written_target(node, node.child_by_field_name("left"), globals_kinds)


@registering(_FINDERS, "update_expression")
def updated(node: Node, globals_kinds: Globals) -> Mutation | None:
    return written_target(node, node.child_by_field_name("argument"), globals_kinds)


@registering(_FINDERS, "delete_statement", "unary_expression")
def deleted(node: Node, globals_kinds: Globals) -> Mutation | None:
    if node.type == "unary_expression" and node_text(node.child_by_field_name("operator")) != "delete":
        return None
    target = node.child_by_field_name("argument") or node.named_children[0]
    targets = target.named_children if target.type == "expression_list" else [target]
    found = (written_target(node, each, globals_kinds) for each in targets)
    return next((mutation for mutation in found if mutation is not None), None)


@registering(_FINDERS, *CALL_KINDS)
def called(node: Node, globals_kinds: Globals) -> Mutation | None:
    callee = node.child_by_field_name("function")
    if callee is None or callee.type not in METHOD_CALLEE_KINDS:
        return None
    receiver = callee.child_by_field_name("object")
    method = node_text(callee.child_by_field_name("attribute") or callee.child_by_field_name("property"))
    if not any(method in METHODS_BY_KIND.get(kind, ()) for kind in kinds_of(globals_kinds, receiver)):
        return None
    return Mutation(node, node_text(receiver) or "", f"calls .{method}() on")


def find_mutation(node: Node, globals_kinds: Globals) -> Mutation | None:
    finder = _FINDERS.get(node.type)
    return None if finder is None else finder(node, globals_kinds)
