from collections.abc import Iterator

from tree_sitter import Node

from pristine.checks.boundaries.execution.swallowed_failures import (
    NARROW_HINT,
    body_text,
    detects,
    logged_default,
    swallow,
)
from pristine.reports.findings import Finding, Severity
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.parsing import ParsedFile, all_nodes

SCRIPT_EMPTY_BODIES = frozenset(
    {"", "return", "return null", "return undefined", "return []", "return {}", 'return ""', "return ''", "return ``"}
)
LOGGED_DEFAULTS = SCRIPT_EMPTY_BODIES - {"", "return"} | {"return false", "return 0"}


def hidden_shape(body: Node) -> str | None:
    text = body_text(body)
    if text == "":
        return "is empty"
    if text in SCRIPT_EMPTY_BODIES:
        return f"only does '{text}'"
    result = logged_default(body, LOGGED_DEFAULTS)
    return None if result is None else f"only logs, then does '{result}'"


@detects(*SCRIPT_LANGUAGES)
def script_swallows(parsed: ParsedFile) -> Iterator[Finding]:
    for clause in (node for node in all_nodes(parsed.root) if node.type == "catch_clause"):
        shape = hidden_shape(clause.child_by_field_name("body") or clause)
        if shape is not None:
            yield swallow(
                parsed, clause, Severity.WARNING, f"catch block {shape}, which hides the failure; {NARROW_HINT}"
            )
