import ast
import warnings
from collections.abc import Iterator
from dataclasses import dataclass

from pristine.imports.python_statements import UNPARSABLE_SOURCE_ERRORS

MINIMUM_STATEMENTS = 6
EXEMPT_DECORATORS = frozenset({"overload", "abstractmethod"})
PROTOCOL_BASE = "Protocol"
BLOCK_FIELDS = ("body", "orelse", "finalbody", "handlers", "cases")

type FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class FunctionBody:
    path: str
    line: int
    name: str
    statements: list[ast.stmt]

    @property
    def shape(self) -> str:
        return "\n".join(ast.dump(statement) for statement in self.statements)


def expression_name(expression: ast.expr) -> str | None:
    if isinstance(expression, ast.Call | ast.Subscript):
        return expression_name(expression.func if isinstance(expression, ast.Call) else expression.value)
    if isinstance(expression, ast.Attribute):
        return expression.attr
    return expression.id if isinstance(expression, ast.Name) else None


def is_protocol(node: ast.AST) -> bool:
    return isinstance(node, ast.ClassDef) and any(expression_name(base) == PROTOCOL_BASE for base in node.bases)


def defined_functions(node: ast.AST) -> Iterator[FunctionNode]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            yield child
        elif not isinstance(child, ast.expr) and not is_protocol(child):
            yield from defined_functions(child)


def body_statements(function: FunctionNode) -> list[ast.stmt]:
    has_docstring = ast.get_docstring(function, clean=False) is not None
    return function.body[1:] if has_docstring else function.body


def nested_blocks(node: ast.AST) -> list[ast.AST]:
    return [child for field in BLOCK_FIELDS for child in getattr(node, field, ())]


def statement_count(nodes: list[ast.AST]) -> int:
    return sum(isinstance(node, ast.stmt) + statement_count(nested_blocks(node)) for node in nodes)


def clone_candidate(path: str, function: FunctionNode) -> FunctionBody | None:
    if any(expression_name(decorator) in EXEMPT_DECORATORS for decorator in function.decorator_list):
        return None
    statements = body_statements(function)
    if statement_count(list[ast.AST](statements)) < MINIMUM_STATEMENTS:
        return None
    return FunctionBody(path, function.lineno, function.name, statements)


def parsed_module(text: str) -> ast.Module | None:
    with warnings.catch_warnings(action="ignore"):
        try:
            return ast.parse(text)
        except UNPARSABLE_SOURCE_ERRORS:
            return None


def function_bodies(path: str, text: str, lines: set[int]) -> list[FunctionBody]:
    module = parsed_module(text)
    functions = defined_functions(module) if module is not None else iter(())
    candidates = (clone_candidate(path, function) for function in functions if function.lineno in lines)
    return [candidate for candidate in candidates if candidate is not None]
