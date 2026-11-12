from collections import Counter
from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.checks.composition.concrete_inheritance.classes import (
    SCRIPT_LANGUAGES,
    base_name,
    members,
    module_classes,
    ordinary_method,
    plain_header,
    statements,
)
from pristine.checks.composition.concrete_inheritance.python import (
    CHECK_ID,
    EXTENSION_NAME,
    MESSAGE,
    MIN_BEHAVIOR_STATEMENTS,
)
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text

CONSTANT_KINDS = frozenset({"null", "true", "false", "number", "string", "array", "object"})


def methods(node: Node) -> dict[str, Node]:
    return {
        node_text(member.child_by_field_name("name")) or "": member
        for member in members(node)
        if ordinary_method(member)
    }


def is_stub(method: Node) -> bool:
    body = statements(method)
    if not body:
        return True
    if len(body) != 1:
        return False
    statement = body[0]
    values = statement.named_children
    return statement.type == "throw_statement" or (
        statement.type == "return_statement" and (not values or values[0].type in CONSTANT_KINDS)
    )


def concrete(node: Node, name: str) -> bool:
    return (
        plain_header(node)
        and EXTENSION_NAME.match(name) is None
        and not any(child.type == "decorator" for child in all_nodes(node))
        and not any(
            member.type in {"abstract_method_signature", "method_signature", "decorator"} for member in members(node)
        )
        and not any(is_stub(method) for method in methods(node).values())
    )


def check_concrete_inheritance(parsed: ParsedFile) -> list[Finding]:
    if parsed.language not in SCRIPT_LANGUAGES or is_test_path(PurePath(parsed.path)):
        return []
    classes = module_classes(parsed)
    counts = Counter(
        base_name(node) for node in parsed.nodes_of("class_declaration", "class", "abstract_class_declaration")
    )
    findings = []
    for name, node in classes.items():
        base = base_name(node)
        if base not in classes or counts[base] != 1 or not concrete(classes[base], base):
            continue
        inherited = methods(classes[base])
        overridden = sorted(methods(node).keys() & inherited.keys())
        method = next((key for key in overridden if len(statements(inherited[key])) >= MIN_BEHAVIOR_STATEMENTS), None)
        if method is not None:
            message = MESSAGE.format(name=name, base=base, method=method)
            findings.append(Finding(parsed.path, line_of(node), CHECK_ID, Severity.WARNING, message))
    return findings
