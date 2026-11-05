from collections.abc import Iterator

from tree_sitter import Node

from pristine.checks.swallowed_failures import PROPAGATE_HINT, body_text, detects, is_expected, normalized, swallow
from pristine.findings import Finding, Severity
from pristine.parsing import ParsedFile, all_nodes

TYPED_CATCH_KINDS = frozenset({"catch_clause", "catch_block"})
TYPED_CATCH_BODY_KINDS = frozenset({"block", "statements"})
TYPE_NAME_KINDS = frozenset({"type_identifier", "identifier"})


def is_silent_catch(clause: Node) -> bool:
    header = [child for child in clause.named_children if child.type not in TYPED_CATCH_BODY_KINDS]
    names = {normalized(node) for child in header for node in all_nodes(child) if node.type in TYPE_NAME_KINDS}
    body = clause.child_by_field_name("body")
    is_empty = body_text(body) == "" if body else len(header) == len(clause.named_children)
    return is_empty and not any(is_expected(name) for name in names)


@detects("java", "csharp", "kotlin")
def typed_catch_swallows(parsed: ParsedFile) -> Iterator[Finding]:
    for clause in (node for node in all_nodes(parsed.root) if node.type in TYPED_CATCH_KINDS and is_silent_catch(node)):
        yield swallow(parsed, clause, Severity.WARNING, f"empty catch block hides the failure; {PROPAGATE_HINT}")
