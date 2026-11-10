from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceFile:
    path: str
    text: str


@dataclass(frozen=True)
class ImportEdge:
    source: str
    target: str
    line: int


type ImportReader = Callable[[list[SourceFile]], list[ImportEdge]]
