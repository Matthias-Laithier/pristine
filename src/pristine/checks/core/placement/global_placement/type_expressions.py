from tree_sitter import Node

from pristine.syntax.parsing import node_text
from pristine.syntax.python_calls import qualified_callee

TYPING_MODULES = ("typing.", "typing_extensions.", "collections.abc.")
BUILTIN_TYPES = frozenset({"dict", "list", "set", "frozenset", "tuple", "type", "str", "int", "float", "bool", "bytes"})
TYPE_CONSTRUCTORS = frozenset(
    f"{module}{name}"
    for module in TYPING_MODULES[:2]
    for name in ("TypeVar", "ParamSpec", "TypeVarTuple", "NewType", "TypedDict", "NamedTuple")
) | {"pydantic.create_model"}
TYPE_REFERENCE_KINDS = frozenset({"identifier", "attribute"})
UNION_OPERATOR = "|"


def is_type_reference(node: Node | None, imports: dict[str, str]) -> bool:
    text = node_text(node) if node is not None and node.type in TYPE_REFERENCE_KINDS else None
    if text is None:
        return False
    return text in BUILTIN_TYPES or (qualified_callee(text, imports) or "").startswith(TYPING_MODULES)


def union_members(node: Node) -> list[Node]:
    operator = node_text(node.child_by_field_name("operator"))
    if node.type != "binary_operator" or operator != UNION_OPERATOR:
        return [node]
    return [member for side in ("left", "right") for member in union_members(node.child_by_field_name(side) or node)]


def is_type_expression(node: Node | None, imports: dict[str, str]) -> bool:
    if node is None:
        return False
    if node.type == "subscript":
        return is_type_reference(node.child_by_field_name("value"), imports)
    if node.type == "call":
        callee = node_text(node.child_by_field_name("function")) or ""
        return qualified_callee(callee, imports) in TYPE_CONSTRUCTORS
    if node.type == "binary_operator":
        members = union_members(node)
        if len(members) == 1:
            return False
        return any(member.type == "none" or is_type_expression(member, imports) for member in members)
    return is_type_reference(node, imports)
