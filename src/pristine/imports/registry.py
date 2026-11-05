from collections.abc import Callable
from dataclasses import dataclass
from functools import cache

from pristine.package_modules import import_package_modules
from pristine.registration import registering

READERS_PACKAGE = "pristine.imports"


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

_READERS: dict[str, ImportReader] = {}


def reads_imports(*suffixes: str) -> Callable[[ImportReader], ImportReader]:
    return registering(_READERS, *suffixes)


@cache
def load_reader_modules() -> None:
    import_package_modules(READERS_PACKAGE)


def reader_for(suffix: str) -> ImportReader | None:
    load_reader_modules()
    return _READERS.get(suffix)
