import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from tree_sitter import Node

from pristine.syntax.parsing import node_text

RECEIVER = "<receiver>"
DOTTED_PATH = re.compile(r"[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)+")

type CalleePaths = Callable[[Node], set[tuple[str, ...]]]


@dataclass(frozen=True)
class InjectedClient:
    scope: Node
    path: tuple[str, ...]
    entry_point: str
    line: int


def dotted_path(callee: Node | None) -> tuple[str, ...] | None:
    text = "".join((node_text(callee) or "").split())
    return tuple(text.split(".")) if DOTTED_PATH.fullmatch(text) else None


def is_called(injected: InjectedClient, paths: set[tuple[str, ...]]) -> bool:
    size = len(injected.path)
    return any(len(path) > size and path[:size] == injected.path for path in paths)


def called_injections(injections: Iterable[InjectedClient], callee_paths: CalleePaths) -> Iterator[tuple[str, int]]:
    for injected in injections:
        if is_called(injected, callee_paths(injected.scope)):
            yield injected.entry_point, injected.line


def no_injected_clients(root: Node) -> Iterator[tuple[str, int]]:
    yield from ()
