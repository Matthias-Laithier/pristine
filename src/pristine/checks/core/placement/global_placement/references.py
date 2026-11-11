lazy from tree_sitter import Node

from pristine.syntax.nodes import COMPREHENSION_KINDS, NESTED_SCOPE_KINDS
from pristine.syntax.parsing import all_nodes, node_text
from pristine.syntax.python_calls import IMPORT_KINDS, imported_names
from pristine.syntax.python_scopes import own_nodes, parameters

LOCAL_BINDING_KINDS = frozenset(
    {
        "assignment",
        "augmented_assignment",
        "named_expression",
        "for_statement",
        "for_in_clause",
        "function_definition",
        "class_definition",
        "as_pattern",
    }
)
REFERENCE_SCOPES = NESTED_SCOPE_KINDS | COMPREHENSION_KINDS
MUTATION_TARGET_KINDS = frozenset({"attribute", "subscript", "member_expression", "subscript_expression"})
NAME_FIELDS = ("name", "left", "alias")


def identifiers(node: Node) -> set[str]:
    return {
        node_text(child) or ""
        for child in all_nodes(node)
        if "identifier" in child.type
        and (child.parent is None or child.parent.child_by_field_name("attribute") != child)
    }


def bound_names(binding: Node) -> set[str]:
    targets = [target for field_name in NAME_FIELDS for target in binding.children_by_field_name(field_name)]
    if any(target.type in MUTATION_TARGET_KINDS for target in targets):
        return set()
    return {name for target in targets for name in identifiers(target)}


def local_bindings(node: Node, members: list[Node]) -> set[str]:
    names = set(parameters(node)) | {
        name for member in members if member.type in LOCAL_BINDING_KINDS for name in bound_names(member)
    }
    return names | {name for member in members if member.type in IMPORT_KINDS for name in imported_names(member)}


def signature_references(node: Node) -> set[str]:
    holders = [(node, ("superclasses", "return_type"))]
    holders.extend((parameter, ("value", "type")) for parameter in parameters(node).values())
    return {
        name
        for holder, fields in holders
        for field_name in fields
        for child in holder.children_by_field_name(field_name)
        for name in identifiers(child)
    }


def module_references(node: Node, shadowed: frozenset[str] = frozenset()) -> set[str]:
    if node.type not in REFERENCE_SCOPES:
        return identifiers(node) - shadowed
    body = node.child_by_field_name("body")
    members = list(own_nodes(node if node.type in COMPREHENSION_KINDS else body or node, REFERENCE_SCOPES))
    masked = shadowed | local_bindings(node, members)
    references = {
        node_text(member) or ""
        for member in members
        if member.type == "identifier"
        and (member.parent is None or member.parent.child_by_field_name("attribute") != member)
    } - masked
    for member in members:
        if member.type in REFERENCE_SCOPES:
            enclosing = shadowed if node.type == "class_definition" else frozenset(masked)
            references |= module_references(member, enclosing)
    return references | (signature_references(node) - shadowed)
