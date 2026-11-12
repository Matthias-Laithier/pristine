from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.checks.boundaries.execution.swallowed_failures.handlers import (
    NARROW_HINT,
    HandlerScope,
    body_text,
    logged_default,
    returned_values,
    swallow,
)
from pristine.checks.boundaries.execution.swallowed_failures.script_scope import script_scope
from pristine.reports.findings import Finding, Severity
from pristine.syntax.parsing import ParsedFile

SCRIPT_EMPTY_BODIES = frozenset(
    {"", "return", "return null", "return undefined", "return []", "return {}", 'return ""', "return ''", "return ``"}
)
LOGGED_DEFAULTS = SCRIPT_EMPTY_BODIES - {"", "return"} | {"return false", "return 0"}


def hidden_shape(body: Node, scope: HandlerScope) -> str | None:
    text = body_text(body)
    if text == "":
        return "is empty"
    if text in SCRIPT_EMPTY_BODIES:
        return f"only does '{text}'"
    result = logged_default(body, LOGGED_DEFAULTS, scope)
    return None if result is None else f"only logs, then does '{result}'"


def script_swallows(parsed: ParsedFile) -> Iterator[Finding]:
    scope = script_scope(parsed, returned_values(LOGGED_DEFAULTS))
    for clause in parsed.nodes_of("catch_clause"):
        shape = hidden_shape(clause.child_by_field_name("body") or clause, scope)
        if shape is not None:
            yield swallow(
                parsed, clause, Severity.WARNING, f"catch block {shape}, which hides the failure; {NARROW_HINT}"
            )
