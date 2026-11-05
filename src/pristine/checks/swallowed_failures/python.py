from collections.abc import Iterator

from tree_sitter import Node

from pristine.checks.swallowed_failures import (
    NARROW_HINT,
    PROPAGATE_HINT,
    body_text,
    detects,
    is_expected,
    logged_default,
    normalized,
    swallow,
)
from pristine.findings import Finding, Severity
from pristine.parsing import ParsedFile, all_nodes

BARE_EXCEPT = ""
BROAD_EXCEPTIONS = frozenset({BARE_EXCEPT, "Exception", "BaseException"})
SILENT_BODIES = frozenset({"pass", "..."})
EMPTY_RESULT_BODIES = frozenset(
    {"continue", "return", "return None", "return []", "return {}", 'return ""', "return ''", "return ()"}
    | {"return set()", "return False"}
)
LOGGED_DEFAULTS = EMPTY_RESULT_BODIES - {"continue", "return"} | {"return 0"}


def caught_names(caught: Node | None) -> frozenset[str]:
    if caught is not None and caught.type == "as_pattern":
        caught = caught.named_children[0]
    if caught is None:
        return frozenset({BARE_EXCEPT})
    names = normalized(caught).strip("()").split(",")
    return frozenset(name.strip().rsplit(".", 1)[-1] for name in names)


def falls_back(clause: Node) -> bool:
    attempt = clause.parent
    body = None if attempt is None else attempt.child_by_field_name("body")
    if attempt is None or body is None:
        return False
    has_else = any(child.type == "else_clause" for child in attempt.named_children)
    return has_else or any(node.type == "return_statement" for node in all_nodes(body))


def python_verdict(clause: Node, names: frozenset[str], body: str | None) -> tuple[Severity, str] | None:
    is_broad = bool(names & BROAD_EXCEPTIONS)
    if body in SILENT_BODIES and is_broad:
        return Severity.ERROR, f"swallows every failure with '{body}'; catch only what this code can recover from"
    is_unexpected = not all(is_expected(name) for name in names)
    if body in SILENT_BODIES and is_unexpected and not falls_back(clause):
        return Severity.WARNING, f"discards the failure with '{body}'; {PROPAGATE_HINT}, or state it with suppress"
    if body in EMPTY_RESULT_BODIES and is_broad:
        return Severity.WARNING, f"turns every failure into '{body}'; {PROPAGATE_HINT}"
    return None


def logged_verdict(names: frozenset[str], block: Node) -> tuple[Severity, str] | None:
    result = None if all(is_expected(name) for name in names) else logged_default(block, LOGGED_DEFAULTS)
    if result is None:
        return None
    return Severity.WARNING, f"only logs, then does '{result}', which hides the failure; {NARROW_HINT}"


@detects("python")
def python_swallows(parsed: ParsedFile) -> Iterator[Finding]:
    for clause in (node for node in all_nodes(parsed.root) if node.type == "except_clause"):
        caught = clause.child_by_field_name("value")
        names, block = caught_names(caught), clause.named_children[-1]
        verdict = python_verdict(clause, names, body_text(block)) or logged_verdict(names, block)
        if verdict is not None:
            head = "except" if caught is None else f"except {normalized(caught)}"
            yield swallow(parsed, clause, verdict[0], f"'{head}' {verdict[1]}")
