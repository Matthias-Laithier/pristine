from dataclasses import dataclass

lazy from tree_sitter import Node

from pristine.syntax.calls import BoundedCall


@dataclass(frozen=True)
class Violation:
    node: Node
    callee: str
    call: BoundedCall
