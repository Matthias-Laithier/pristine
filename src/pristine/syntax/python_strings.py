from collections.abc import Callable
from dataclasses import dataclass

lazy from tree_sitter import Node

from pristine.registration import registering
from pristine.syntax.node_types import SyntaxNode
from pristine.syntax.parsing import node_text

STRING_KINDS = frozenset({"string", "concatenated_string"})
FORMAT_METHOD = "format"


@dataclass(frozen=True)
class BuiltString:
    method: str
    template: SyntaxNode
    values: list[SyntaxNode]


_READERS: dict[str, Callable[[Node], BuiltString | None]] = {}


def built_string(node: Node) -> BuiltString | None:
    reader = _READERS.get(node.type)
    return None if reader is None else reader(node)


def interpolations(node: Node) -> list[Node]:
    if node.type == "concatenated_string":
        return [inner for part in node.named_children for inner in interpolations(part)]
    expressions = (child.child_by_field_name("expression") for child in node.named_children)
    return [expression for expression in expressions if expression is not None] if node.type == "string" else []


def is_constant_string(node: Node) -> bool:
    return node.type in STRING_KINDS and not interpolations(node)


@registering(_READERS, *STRING_KINDS)
def interpolated_string(node: Node) -> BuiltString | None:
    values = interpolations(node)
    return BuiltString("an f-string", node, values) if values else None


@registering(_READERS, "call")
def format_call(node: Node) -> BuiltString | None:
    function = node.child_by_field_name("function")
    arguments = node.child_by_field_name("arguments")
    if function is None or arguments is None or node_text(function.child_by_field_name("attribute")) != FORMAT_METHOD:
        return None
    receiver = function.child_by_field_name("object")
    if receiver is None or receiver.type not in STRING_KINDS:
        return None
    values = [argument.child_by_field_name("value") or argument for argument in arguments.named_children]
    return BuiltString("str.format", receiver, values)


@registering(_READERS, "binary_operator")
def operator_string(node: Node) -> BuiltString | None:
    left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
    operator = node_text(node.child_by_field_name("operator"))
    if operator == "%" and left is not None and right is not None and left.type in STRING_KINDS:
        return BuiltString("%-formatting", left, formatted_values(right))
    pieces = operands(node)
    if (
        operator != "+"
        or all(map(is_constant_string, pieces))
        or not any(piece.type in STRING_KINDS for piece in pieces)
    ):
        return None
    values = [inner for piece in pieces for inner in interpolations(piece) or [piece]]
    return BuiltString("string concatenation", pieces[0], values)


def operands(node: Node) -> list[Node]:
    left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
    if node.type != "binary_operator" or left is None or right is None:
        return [node]
    is_concatenation = node_text(node.child_by_field_name("operator")) == "+"
    return [*operands(left), right] if is_concatenation else [node]


def formatted_values(node: Node) -> list[Node]:
    if node.type == "tuple":
        return node.named_children
    if node.type == "dictionary":
        return [pair.child_by_field_name("value") or pair for pair in node.named_children]
    return [node]
