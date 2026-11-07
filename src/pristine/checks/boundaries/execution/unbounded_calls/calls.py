from dataclasses import dataclass

from pristine.syntax.calls import BoundedCall
from pristine.syntax.node_types import SyntaxNode


@dataclass(frozen=True)
class Violation:
    node: SyntaxNode
    callee: str
    call: BoundedCall
