import ast
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from pristine.registration import registering

DYNAMIC_IMPORT_FUNCTIONS = frozenset({"import_module", "__import__"})
UNPARSABLE_SOURCE_ERRORS = (SyntaxError, ValueError, RecursionError, MemoryError)
WILDCARD = "*"


@dataclass(frozen=True)
class PythonImport:
    line: int
    level: int
    module: str
    names: tuple[str, ...]


type StatementReader = Callable[[Any], Iterator[PythonImport]]

_STATEMENT_READERS: dict[type[ast.AST], StatementReader] = {}


@registering(_STATEMENT_READERS, ast.Import)
def read_import(node: ast.Import) -> Iterator[PythonImport]:
    yield from (PythonImport(node.lineno, 0, alias.name, ()) for alias in node.names)


@registering(_STATEMENT_READERS, ast.ImportFrom)
def read_import_from(node: ast.ImportFrom) -> Iterator[PythonImport]:
    names = tuple(alias.name for alias in node.names if alias.name != WILDCARD)
    yield PythonImport(node.lineno, node.level, node.module or "", names)


def called_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return call.func.id if isinstance(call.func, ast.Name) else None


def literal_module_argument(call: ast.Call) -> str | None:
    if not call.args or not isinstance(call.args[0], ast.Constant):
        return None
    module = call.args[0].value
    return module if isinstance(module, str) and module and not module.startswith(".") else None


@registering(_STATEMENT_READERS, ast.Call)
def read_dynamic_import(node: ast.Call) -> Iterator[PythonImport]:
    module = literal_module_argument(node) if called_name(node) in DYNAMIC_IMPORT_FUNCTIONS else None
    if module is not None:
        yield PythonImport(node.lineno, 0, module, ())


def python_imports(text: str) -> list[PythonImport]:
    try:
        tree = ast.parse(text)
    except UNPARSABLE_SOURCE_ERRORS:
        return []
    imports = []
    for node in ast.walk(tree):
        reader = _STATEMENT_READERS.get(type(node))
        if reader is not None:
            imports.extend(reader(node))
    return imports
