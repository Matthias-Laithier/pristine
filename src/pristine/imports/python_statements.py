import ast
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass

DYNAMIC_IMPORT_FUNCTIONS = frozenset({"import_module", "__import__"})
IDENTIFIER_NORMALIZATION = "NFKC"
STATEMENT_BLOCKS = ("body", "orelse", "finalbody", "handlers", "cases")
UNPARSABLE_SOURCE_ERRORS = (SyntaxError, ValueError, RecursionError, MemoryError)
WILDCARD = "*"


@dataclass(frozen=True)
class PythonImport:
    line: int
    level: int
    module: str
    names: tuple[str, ...]


def read_import(node: ast.Import) -> Iterator[PythonImport]:
    yield from (PythonImport(node.lineno, 0, alias.name, ()) for alias in node.names)


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


def read_dynamic_import(node: ast.Call) -> Iterator[PythonImport]:
    module = literal_module_argument(node) if called_name(node) in DYNAMIC_IMPORT_FUNCTIONS else None
    if module is not None:
        yield PythonImport(node.lineno, 0, module, ())


def statement_imports(node: ast.AST) -> Iterator[PythonImport]:
    if isinstance(node, ast.Import):
        return read_import(node)
    if isinstance(node, ast.ImportFrom):
        return read_import_from(node)
    return read_dynamic_import(node) if isinstance(node, ast.Call) else iter(())


def nested_statements(node: ast.AST) -> Iterator[ast.AST]:
    blocks = (getattr(node, block, None) for block in STATEMENT_BLOCKS)
    children = (child for block in blocks if isinstance(block, list) for child in block)
    return (child for child in children if isinstance(child, ast.AST))


def statement_nodes(tree: ast.AST) -> Iterator[ast.AST]:
    pending = [tree]
    while pending:
        node = pending.pop()
        yield node
        pending.extend(nested_statements(node))


def may_import_dynamically(text: str) -> bool:
    identifiers = text if text.isascii() else unicodedata.normalize(IDENTIFIER_NORMALIZATION, text)
    return any(function in identifiers for function in DYNAMIC_IMPORT_FUNCTIONS)


def python_imports(text: str) -> list[PythonImport]:
    try:
        tree = ast.parse(text)
    except UNPARSABLE_SOURCE_ERRORS:
        return []
    nodes = ast.walk(tree) if may_import_dynamically(text) else statement_nodes(tree)
    return [found for node in nodes for found in statement_imports(node)]
