import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from tree_sitter import Node

from pristine.checks.registry import FileCheck, register_file_check
from pristine.checks.unbounded_calls.python_calls import import_bindings, qualified_callee
from pristine.findings import Finding, Severity
from pristine.parsing import ParsedFile, all_nodes, line_of, node_text

RULE_ID = "CR-21"
TYPING_MODULES = ("typing", "typing_extensions")
ANY_NAMES = frozenset(f"{module}.Any" for module in TYPING_MODULES)
CAST_NAMES = frozenset(f"{module}.cast" for module in TYPING_MODULES)
ANNOTATION_KIND = "type"
REFERENCE_KINDS = frozenset({"identifier", "attribute"})
SCRIPT_ANY = "any"
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


def python_escapes(root: Node) -> Iterator[Escape]:
    bindings = import_bindings(root)
    nodes = list(all_nodes(root))
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


def script_escapes(root: Node) -> Iterator[Escape]:
    for node in all_nodes(root):
        if node.type == "predefined_type" and node_text(node) == SCRIPT_ANY:
            yield Escape(line_of(node), Severity.ERROR, f"'any' type; {ANY_FIX}")
        if node.type == "non_null_expression":
            message = f"non-null assertion '{node_text(node)}'; {ASSERTION_FIX}"
            yield Escape(line_of(node), Severity.WARNING, message)


def suppressions(parsed: ParsedFile) -> Iterator[Escape]:
    pattern = SUPPRESSIONS.get(parsed.language)
    matches = [] if pattern is None else [(comment.line, pattern.search(comment.text)) for comment in parsed.comments]
    for line, match in matches:
        if match is not None:
            yield Escape(line, Severity.ERROR, f"'{match['directive']}' without an error code; {SUPPRESSION_FIX}")


SCANNERS: dict[str, Callable[[Node], Iterator[Escape]]] = {
    "python": python_escapes,
    "typescript": script_escapes,
    "tsx": script_escapes,
}


def check_type_escapes(parsed: ParsedFile) -> list[Finding]:
    scanner = SCANNERS.get(parsed.language)
    if scanner is None or parsed.path.endswith(DECLARATION_SUFFIXES):
        return []
    escapes = [*scanner(parsed.root), *suppressions(parsed)]
    return [Finding(parsed.path, escape.line, RULE_ID, escape.severity, escape.message) for escape in escapes]


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Type checker escape hatches: Python Any in annotations and bare type: ignore or pyright: ignore "
            "(error), typing.cast (warning); TypeScript any, @ts-ignore, and @ts-nocheck (error), and non-null "
            "assertions (warning). Declaration files are skipped."
        ),
        run=check_type_escapes,
    )
)
