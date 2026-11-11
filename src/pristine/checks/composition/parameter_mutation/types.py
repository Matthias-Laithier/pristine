lazy from tree_sitter import Node

from pristine.syntax.parsing import node_text

COLLECTION_TYPES = {"Array": "array", "Map": "map", "Record": "object"}
NULL_TYPES = frozenset({"null", "undefined"})
ARRAY_MUTATORS = frozenset({"push", "pop", "shift", "unshift", "splice", "sort", "reverse", "fill", "copyWithin"})
MAP_MUTATORS = frozenset({"set", "delete", "clear"})
MUTATORS = {"array": ARRAY_MUTATORS, "map": MAP_MUTATORS, "object": frozenset()}


def collection_kind(node: Node, shadowed: set[str]) -> str | None:
    if node.type in {"type_annotation", "parenthesized_type"} and len(node.named_children) == 1:
        return collection_kind(node.named_children[0], shadowed)
    if node.type == "union_type":
        members = [child for child in node.named_children if node_text(child) not in NULL_TYPES]
        return collection_kind(members[0], shadowed) if len(members) == 1 else None
    if node.type in {"array_type", "tuple_type"}:
        return "array"
    if node.type == "object_type":
        return "object"
    if node.type == "generic_type":
        name = node_text(node.child_by_field_name("name")) or ""
        return COLLECTION_TYPES.get(name) if name not in shadowed else None
    return None


def typed_parameters(function: Node, shadowed: set[str]) -> dict[str, str]:
    parameters = function.child_by_field_name("parameters")
    groups = [] if parameters is None else parameters.named_children
    result = {}
    for group in groups:
        name, annotation = group.child_by_field_name("pattern"), group.child_by_field_name("type")
        kind = collection_kind(annotation, shadowed) if annotation is not None else None
        if name is not None and name.type == "identifier" and kind is not None:
            result[node_text(name) or ""] = kind
    return result
