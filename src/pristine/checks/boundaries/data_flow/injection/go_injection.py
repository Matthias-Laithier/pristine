import re
from collections.abc import Iterator

from tree_sitter import Node

from pristine.checks.boundaries.data_flow.injection.constructed import Injection, starts_with_sql
from pristine.syntax.calls import calls_of
from pristine.syntax.parsing import ParsedFile, node_text

SQL_METHODS = frozenset({"Query", "QueryRow", "Exec", "QueryContext", "QueryRowContext", "ExecContext"})
STRING_KINDS = frozenset({"interpreted_string_literal", "raw_string_literal"})
LITERAL_KINDS = STRING_KINDS | {"int_literal", "float_literal"}
CONTEXT_ARGUMENT = re.compile(r"ctx$|context", re.IGNORECASE)
FORMATTER = "fmt.Sprintf"
NUMBER_FORMATTER_PREFIX = "strconv."
COMMAND_FUNCTIONS = {"exec.Command": 0, "exec.CommandContext": 1}
SHELLS = frozenset({"sh", "bash", "zsh", "/bin/sh", "/bin/bash", "/bin/zsh"})
SHELL_FLAG = "-c"
SHELL_COMMAND_LENGTH = 3
SQL_FIX = "pass values as query arguments, and map identifiers through a fixed literal mapping"
SHELL_FIX = "pass the program and its arguments to exec.Command without a shell"


def literal_text(node: Node) -> str | None:
    return (node_text(node) or "")[1:-1] if node.type in STRING_KINDS else None


def is_trusted(node: Node) -> bool:
    if node.type == "call_expression":
        return (node_text(node.child_by_field_name("function")) or "").startswith(NUMBER_FORMATTER_PREFIX)
    return node.type in LITERAL_KINDS or (
        node.type == "binary_expression" and all(map(is_trusted, node.named_children))
    )


def concatenated(node: Node) -> list[Node]:
    left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
    if (
        node.type != "binary_expression"
        or node_text(node.child_by_field_name("operator")) != "+"
        or not left
        or not right
    ):
        return [node]
    return [*concatenated(left), right]


def is_built_sql(node: Node) -> bool:
    arguments = node.child_by_field_name("arguments")
    is_formatted = node.type == "call_expression" and node_text(node.child_by_field_name("function")) == FORMATTER
    pieces = arguments.named_children if is_formatted and arguments is not None else concatenated(node)
    return len(pieces) > 1 and starts_with_sql(literal_text(pieces[0]) or "") and not all(map(is_trusted, pieces[1:]))


def shell_script(callee: str, arguments: list[Node]) -> Node | None:
    offset = COMMAND_FUNCTIONS.get(callee)
    command = [] if offset is None else arguments[offset : offset + SHELL_COMMAND_LENGTH]
    if (
        len(command) < SHELL_COMMAND_LENGTH
        or literal_text(command[0]) not in SHELLS
        or literal_text(command[1]) != SHELL_FLAG
    ):
        return None
    return command[2]


def call_injection(callee: str, arguments: list[Node]) -> str | None:
    has_context = len(arguments) > 1 and CONTEXT_ARGUMENT.search(node_text(arguments[0]) or "") is not None
    query = arguments[int(has_context)] if arguments else None
    if callee.rpartition(".")[2] in SQL_METHODS and query is not None and is_built_sql(query):
        return f"'{callee}' receives SQL built from non-literal values; {SQL_FIX}"
    script = shell_script(callee, arguments)
    if script is None or is_trusted(script):
        return None
    return f"'{callee}' runs a shell command built from non-literal values; {SHELL_FIX}"


def scan_go(parsed: ParsedFile) -> Iterator[Injection]:
    for node, callee, arguments in calls_of(parsed.root, "call_expression"):
        message = call_injection(callee, arguments)
        if message is not None:
            yield Injection(node, message)
