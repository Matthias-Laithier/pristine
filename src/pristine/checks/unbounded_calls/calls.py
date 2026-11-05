from collections.abc import Iterator
from dataclasses import dataclass

from tree_sitter import Node

from pristine.findings import Severity
from pristine.parsing import all_nodes, node_text

UNKNOWN_ARGUMENT_KINDS = frozenset({"list_splat", "dictionary_splat", "spread_element"})


@dataclass(frozen=True)
class BoundedCall:
    bound: str
    position: int | None
    severity: Severity
    fix: str


@dataclass(frozen=True)
class Violation:
    node: Node
    callee: str
    call: BoundedCall


def calls_of(root: Node, call_kind: str) -> Iterator[tuple[Node, str, list[Node]]]:
    for node in all_nodes(root):
        callee = "".join((node_text(node.child_by_field_name("function")) or "").split())
        arguments = node.child_by_field_name("arguments")
        if node.type == call_kind and arguments is not None:
            yield node, callee, arguments.named_children


def has_unknown_argument(arguments: list[Node]) -> bool:
    return any(argument.type in UNKNOWN_ARGUMENT_KINDS for argument in arguments)
