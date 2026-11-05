from collections.abc import Iterator

from pristine.checks.swallowed_failures import PROPAGATE_HINT, body_text, detects, swallow
from pristine.findings import Finding, Severity
from pristine.parsing import ParsedFile, all_nodes
from pristine.services.grammars import SCRIPT_LANGUAGES

SCRIPT_EMPTY_BODIES = frozenset(
    {"", "return", "return null", "return undefined", "return []", "return {}", 'return ""', "return ''", "return ``"}
)


@detects(*SCRIPT_LANGUAGES)
def script_swallows(parsed: ParsedFile) -> Iterator[Finding]:
    for clause in (node for node in all_nodes(parsed.root) if node.type == "catch_clause"):
        body = body_text(clause.child_by_field_name("body") or clause)
        if body in SCRIPT_EMPTY_BODIES:
            shape = "is empty" if body == "" else f"only does '{body}'"
            yield swallow(parsed, clause, Severity.WARNING, f"catch block {shape}, which hides it; {PROPAGATE_HINT}")
