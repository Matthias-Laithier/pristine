from dataclasses import dataclass

from tree_sitter import Node

from pristine.calls import BoundedCall


@dataclass(frozen=True)
class Violation:
    node: Node
    callee: str
    call: BoundedCall
