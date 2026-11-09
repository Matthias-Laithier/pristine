from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.checks.boundaries.data_flow.injection.constructed import Injection, starts_with_sql
from pristine.checks.boundaries.data_flow.injection.python.values import is_trusted
from pristine.syntax.calls import calls_of
from pristine.syntax.parsing import ParsedFile, node_text
from pristine.syntax.python_calls import positional_arguments
from pristine.syntax.python_strings import STRING_KINDS, built_string

SQL_FUNCTIONS = frozenset(
    {"execute", "executemany", "executescript", "fetch", "fetchrow", "fetchval", "fetch_all", "fetch_one"}
    | {"text", "raw"}
)
SQL_FIX = "pass values as bound parameters, and map identifiers through a fixed literal mapping"


def leading_text(node: Node) -> str:
    head = node.named_children[0] if node.type == "concatenated_string" and node.named_children else node
    parts = head.named_children if head.type == "string" else []
    return node_text(parts[1]) or "" if len(parts) > 1 and parts[1].type == "string_content" else ""


def is_built_sql(node: Node) -> bool:
    built = built_string(node)
    if built is None or built.template.type not in STRING_KINDS:
        return False
    return starts_with_sql(leading_text(built.template)) and not all(map(is_trusted, built.values))


def scan_sql(parsed: ParsedFile) -> Iterator[Injection]:
    for node, callee, arguments in calls_of(parsed, "call"):
        positional = positional_arguments(arguments)
        is_sql_call = callee.rsplit(".", 1)[-1] in SQL_FUNCTIONS and bool(positional)
        if is_sql_call and is_built_sql(positional[0]):
            yield Injection(node, f"'{callee}' receives SQL built from non-literal values; {SQL_FIX}")
