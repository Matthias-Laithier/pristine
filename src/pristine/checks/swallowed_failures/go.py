import re
from collections.abc import Iterator

from tree_sitter import Node

from pristine.checks.swallowed_failures import PROPAGATE_HINT, detects, normalized, statements_of, swallow
from pristine.findings import Finding, Severity
from pristine.match_groups import group_text
from pristine.parsing import ParsedFile, all_nodes

ERROR_NAME = re.compile(r"err(or)?(\d|[A-Z_]\w*)?|\w+Err(or)?\d*")
ERROR_CHECK = re.compile(r"(?P<name>\w+) != nil")
DISCARD = re.compile(r"_ = (?P<name>\w+)")
ZERO_VALUES = frozenset({"nil", "false", "0", '""', "``"})
GO_FUNCTION_KINDS = frozenset({"function_declaration", "method_declaration", "func_literal"})
ERROR_TYPE = "error"


def error_name(node: Node | None, pattern: re.Pattern[str]) -> str | None:
    match = None if node is None else pattern.fullmatch(normalized(node))
    name = None if match is None else group_text(match, "name")
    return name if name is not None and ERROR_NAME.fullmatch(name) else None


def block_statements(block: Node | None) -> list[Node]:
    lists = [] if block is None else [child for child in block.named_children if child.type == "statement_list"]
    return statements_of(lists[0]) if lists else []


def declares_error_result(statement: Node) -> bool:
    function = statement.parent
    while function is not None and function.type not in GO_FUNCTION_KINDS:
        function = function.parent
    result = None if function is None else function.child_by_field_name("result")
    if result is None or result.type != "parameter_list":
        return result is not None and normalized(result) == ERROR_TYPE
    kinds = [parameter.child_by_field_name("type") for parameter in result.named_children]
    return any(kind is not None and normalized(kind) == ERROR_TYPE for kind in kinds)


def returns_nil_error(statement: Node) -> bool:
    if statement.type != "return_statement" or not statement.named_children:
        return False
    values = statement.named_children[0].named_children
    return all(normalized(value) in ZERO_VALUES for value in values) and declares_error_result(statement)


def dropped_by_check(check: Node) -> str | None:
    name = error_name(check.child_by_field_name("condition"), ERROR_CHECK)
    if name is None:
        return None
    statements = block_statements(check.child_by_field_name("consequence"))
    if not statements:
        return f"'if {name} != nil' block is empty and drops the error"
    if len(statements) == 1 and returns_nil_error(statements[0]):
        return f"'if {name} != nil' only does '{normalized(statements[0])}', which reports success and drops the error"
    return None


def dropped_error(node: Node) -> str | None:
    if node.type == "if_statement":
        return dropped_by_check(node)
    name = error_name(node, DISCARD) if node.type == "assignment_statement" else None
    return None if name is None else f"'_ = {name}' drops the error"


@detects("go")
def go_swallows(parsed: ParsedFile) -> Iterator[Finding]:
    for node in all_nodes(parsed.root):
        message = dropped_error(node)
        if message is not None:
            yield swallow(parsed, node, Severity.WARNING, f"{message}; {PROPAGATE_HINT}")
