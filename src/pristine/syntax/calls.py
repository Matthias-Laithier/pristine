from collections.abc import Iterator
from dataclasses import dataclass

lazy from tree_sitter import Node

from pristine.reports.findings import Severity
from pristine.syntax.parsing import ParsedFile, all_nodes, node_text

UNKNOWN_ARGUMENT_KINDS = frozenset({"list_splat", "dictionary_splat", "spread_element"})


@dataclass(frozen=True)
class BoundedCall:
    bound: str
    position: int | None
    severity: Severity
    fix: str


def callee_of(call: Node) -> str:
    return "".join((node_text(call.child_by_field_name("function")) or "").split())


def calls_of(source: Node | ParsedFile, call_kind: str) -> Iterator[tuple[Node, str, list[Node]]]:
    for node in all_nodes(source):
        arguments = node.child_by_field_name("arguments")
        if node.type == call_kind and arguments is not None:
            yield node, callee_of(node), arguments.named_children


def has_unknown_argument(arguments: list[Node]) -> bool:
    return any(argument.type in UNKNOWN_ARGUMENT_KINDS for argument in arguments)
