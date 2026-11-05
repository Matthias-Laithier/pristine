from collections.abc import Iterator

from tree_sitter import Node

from pristine.calls import calls_of
from pristine.checks.injection.constructed import Injection, starts_with_sql
from pristine.checks.injection.python_values import interpolations, is_trusted
from pristine.parsing import node_text
from pristine.python_calls import positional_arguments

SQL_FUNCTIONS = frozenset(
    {"execute", "executemany", "executescript", "fetch", "fetchrow", "fetchval", "fetch_all", "fetch_one"}
    | {"text", "raw"}
)
STRING_KINDS = frozenset({"string", "concatenated_string"})
FORMAT_METHOD = "format"
SQL_FIX = "pass values as bound parameters, and map identifiers through a fixed literal mapping"


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


def format_call_parts(node: Node) -> tuple[Node, list[Node]] | None:
    function = node.child_by_field_name("function")
    arguments = node.child_by_field_name("arguments")
    if function is None or arguments is None or node_text(function.child_by_field_name("attribute")) != FORMAT_METHOD:
        return None
    receiver = function.child_by_field_name("object")
    if receiver is None:
        return None
    values = [argument.child_by_field_name("value") or argument for argument in arguments.named_children]
    return receiver, values


def built_parts(node: Node) -> tuple[Node, list[Node]] | None:
    if node.type in STRING_KINDS:
        return node, interpolations(node)
    if node.type == "call":
        return format_call_parts(node)
    if node.type != "binary_operator":
        return None
    left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
    if node_text(node.child_by_field_name("operator")) == "%" and left is not None and right is not None:
        return left, formatted_values(right)
    pieces = operands(node)
    return pieces[0], [inner for piece in pieces for inner in interpolations(piece) or [piece]]


def leading_text(node: Node) -> str:
    head = node.named_children[0] if node.type == "concatenated_string" and node.named_children else node
    parts = head.named_children if head.type == "string" else []
    return node_text(parts[1]) or "" if len(parts) > 1 and parts[1].type == "string_content" else ""


def is_built_sql(node: Node) -> bool:
    parts = built_parts(node)
    if parts is None or parts[0].type not in STRING_KINDS:
        return False
    head, values = parts
    return starts_with_sql(leading_text(head)) and not all(map(is_trusted, values))


def scan_sql(root: Node) -> Iterator[Injection]:
    for node, callee, arguments in calls_of(root, "call"):
        positional = positional_arguments(arguments)
        is_sql_call = callee.rsplit(".", 1)[-1] in SQL_FUNCTIONS and bool(positional)
        if is_sql_call and is_built_sql(positional[0]):
            yield Injection(node, f"'{callee}' receives SQL built from non-literal values; {SQL_FIX}")
