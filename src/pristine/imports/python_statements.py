import ast
from collections.abc import Iterator
from dataclasses import dataclass
from functools import singledispatch

DYNAMIC_IMPORT_FUNCTIONS = frozenset({"import_module", "__import__"})
UNPARSABLE_SOURCE_ERRORS = (SyntaxError, ValueError, RecursionError, MemoryError)
WILDCARD = "*"


@dataclass(frozen=True)
class PythonImport:
    line: int
    level: int
    module: str
    names: tuple[str, ...]


@singledispatch
def statement_imports(node: ast.AST) -> Iterator[PythonImport]:
    yield from ()


@statement_imports.register
def read_import(node: ast.Import) -> Iterator[PythonImport]:
    yield from (PythonImport(node.lineno, 0, alias.name, ()) for alias in node.names)


@statement_imports.register
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


@statement_imports.register
def read_dynamic_import(node: ast.Call) -> Iterator[PythonImport]:
    module = literal_module_argument(node) if called_name(node) in DYNAMIC_IMPORT_FUNCTIONS else None
    if module is not None:
        yield PythonImport(node.lineno, 0, module, ())


def python_imports(text: str) -> list[PythonImport]:
    try:
        tree = ast.parse(text)
    except UNPARSABLE_SOURCE_ERRORS:
        return []
    return [found for node in ast.walk(tree) for found in statement_imports(node)]
