import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

lazy from tree_sitter import Node

from pristine.checks.registry import FileCheck, register_file_check
from pristine.reports.findings import Finding, Severity
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text
from pristine.syntax.python_calls import import_bindings, qualified_callee

RULE_ID = "CR-21"
TYPING_MODULES = ("typing", "typing_extensions")
ANY_NAMES = frozenset(f"{module}.Any" for module in TYPING_MODULES)
CAST_NAMES = frozenset(f"{module}.cast" for module in TYPING_MODULES)
ANNOTATION_KIND = "type"
REFERENCE_KINDS = frozenset({"identifier", "attribute"})
SCRIPT_ANY = "any"
SCRIPT_UNKNOWN = "unknown"
ASSERTION_KINDS = frozenset({"as_expression", "type_assertion"})
ASSERTION_PART_COUNT = 2
UNKNOWN_COMPOSITES = frozenset({"parenthesized_type", "union_type", "intersection_type"})
DECLARATION_SUFFIXES = (".d.ts", ".d.mts", ".d.cts")
SCRIPT_SUPPRESSION = re.compile(r"(?:^|//|/\*)\s*(?P<directive>@ts-(?:ignore|nocheck))\b")
SUPPRESSIONS = {
    "python": re.compile(r"(?:^|#)\s*(?P<directive>(?:type|pyright):\s*ignore)\b(?!\[)"),
    "typescript": SCRIPT_SUPPRESSION,
    "tsx": SCRIPT_SUPPRESSION,
}
ANY_FIX = "annotate the real type, or 'object' or 'unknown' narrowed by parsing"
CAST_FIX = "narrow with a runtime check, or parse the value"
SUPPRESSION_FIX = "fix the type error, or name its error code inside the service wrapping the untyped dependency"
ASSERTION_FIX = "narrow with an explicit check that handles the missing value"


@dataclass(frozen=True)
class Escape:
    line: int
    severity: Severity
    message: str


def resolves_to(node: Node | None, names: frozenset[str], bindings: dict[str, str]) -> bool:
    is_member = node is not None and node.parent is not None and node.parent.type == "attribute"
    if node is None or node.type not in REFERENCE_KINDS or is_member:
        return False
    return qualified_callee(node_text(node) or "", bindings) in names


def python_escapes(parsed: ParsedFile) -> Iterator[Escape]:
    bindings = import_bindings(parsed)
    nodes = list(all_nodes(parsed))
    annotations = [node for node in nodes if node.type == ANNOTATION_KIND]
    any_uses = {
        inner.start_byte: inner
        for annotation in annotations
        for inner in all_nodes(annotation)
        if resolves_to(inner, ANY_NAMES, bindings)
    }
    for use in any_uses.values():
        yield Escape(line_of(use), Severity.ERROR, f"'{node_text(use)}' in an annotation; {ANY_FIX}")
    for node in nodes:
        if node.type == "call" and resolves_to(node.child_by_field_name("function"), CAST_NAMES, bindings):
            yield Escape(
                line_of(node), Severity.WARNING, f"'cast' asserts a type the checker cannot verify; {CAST_FIX}"
            )


def script_escapes(parsed: ParsedFile) -> Iterator[Escape]:
    for node in all_nodes(parsed):
        if node.type == "predefined_type" and node_text(node) == SCRIPT_ANY:
            yield Escape(line_of(node), Severity.ERROR, f"'any' type; {ANY_FIX}")
        if node.type == "non_null_expression":
            message = f"non-null assertion '{node_text(node)}'; {ASSERTION_FIX}"
            yield Escape(line_of(node), Severity.WARNING, message)
        if double_assertion_through_unknown(node):
            message = f"double assertion through 'unknown' asserts a type the checker cannot verify; {CAST_FIX}"
            yield Escape(line_of(node), Severity.WARNING, message)


def assertion_parts(node: Node) -> tuple[Node, Node]:
    expression, target = node.named_children[0], node.named_children[-1]
    if node.type == "type_assertion":
        target, expression = expression.named_children[0], target
    while expression.type == "parenthesized_expression":
        expression = expression.named_children[0]
    return expression, target


def double_assertion_through_unknown(node: Node) -> bool:
    if node.type not in ASSERTION_KINDS or len(node.named_children) < ASSERTION_PART_COUNT:
        return False
    expression, target = assertion_parts(node)
    if expression.type not in ASSERTION_KINDS or len(expression.named_children) < ASSERTION_PART_COUNT:
        return False
    _, intermediate = assertion_parts(expression)
    return remains_unknown(intermediate) and not remains_unknown(target)


def remains_unknown(node: Node) -> bool:
    results: dict[int, bool] = {}
    for current in reversed(list(all_nodes(node))):
        values = [results[child.id] for child in current.named_children] if current.type in UNKNOWN_COMPOSITES else []
        combined = any(values) if current.type == "union_type" else bool(values) and all(values)
        results[current.id] = combined or current.type == "predefined_type" and node_text(current) == SCRIPT_UNKNOWN
    return results[node.id]


def suppressions(parsed: ParsedFile) -> Iterator[Escape]:
    pattern = SUPPRESSIONS.get(parsed.language)
    matches = [] if pattern is None else [(comment.line, pattern.search(comment.text)) for comment in parsed.comments]
    for line, match in matches:
        if match is not None:
            yield Escape(line, Severity.ERROR, f"'{match['directive']}' without an error code; {SUPPRESSION_FIX}")


SCANNERS: dict[str, Callable[[ParsedFile], Iterator[Escape]]] = {
    "python": python_escapes,
    "typescript": script_escapes,
    "tsx": script_escapes,
}


def check_type_escapes(parsed: ParsedFile) -> list[Finding]:
    scanner = SCANNERS.get(parsed.language)
    if scanner is None or parsed.path.endswith(DECLARATION_SUFFIXES):
        return []
    escapes = [*scanner(parsed), *suppressions(parsed)]
    return [Finding(parsed.path, escape.line, RULE_ID, escape.severity, escape.message) for escape in escapes]


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Type checker escape hatches: Python Any in annotations and bare type: ignore or pyright: ignore "
            "(error), typing.cast (warning); TypeScript any, @ts-ignore, and @ts-nocheck (error), and non-null "
            "assertions and double assertions through unknown (warning). Declaration files are skipped."
        ),
        run=check_type_escapes,
    )
)
