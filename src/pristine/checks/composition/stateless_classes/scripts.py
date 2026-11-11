from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.checks.composition.concrete_inheritance.classes import (
    SCRIPT_LANGUAGES,
    base_name,
    members,
    module_classes,
    plain_header,
    statements,
)
from pristine.checks.composition.stateless_classes.python import CHECK_ID, MESSAGE
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text


def static_method(node: Node) -> bool:
    name = node.child_by_field_name("name")
    return (
        node.type == "method_definition"
        and any(child.type == "static" for child in node.children)
        and not any(child.type in {"decorator", "get", "set"} for child in node.children)
        and name is not None
        and name.type in {"property_identifier", "private_property_identifier"}
        and bool(statements(node))
        and not any(child.type in {"this", "super"} for child in all_nodes(node))
    )


def is_public(method: Node) -> bool:
    name = node_text(method.child_by_field_name("name")) or ""
    private = any(node_text(child) in {"private", "protected"} for child in method.named_children)
    return not private and not name.startswith(("_", "#"))


def namespace_reference(node: Node) -> bool:
    parent = node.parent
    if parent is None or parent.type != "member_expression" or parent.child_by_field_name("object") != node:
        return False
    holder = parent.parent
    writes = {"assignment_expression", "augmented_assignment_expression", "update_expression", "unary_expression"}
    return holder is None or holder.type not in writes


def namespace_only(parsed: ParsedFile, node: Node, name: str) -> bool:
    declaration = node.child_by_field_name("name")
    references = [
        found
        for found in all_nodes(parsed)
        if found != declaration and found.type in {"identifier", "type_identifier"} and node_text(found) == name
    ]
    mentioned = any(found.type == "string" and name in (node_text(found) or "") for found in all_nodes(parsed))
    return not mentioned and all(namespace_reference(found) for found in references)


def check_stateless_classes(parsed: ParsedFile) -> list[Finding]:
    if parsed.language not in SCRIPT_LANGUAGES or is_test_path(PurePath(parsed.path)):
        return []
    extended = {
        base_name(node)
        for node in all_nodes(parsed)
        if node.type in {"class_declaration", "class", "abstract_class_declaration"}
    }
    findings = []
    for name, node in module_classes(parsed).items():
        methods = members(node)
        eligible = (
            name not in extended
            and plain_header(node)
            and methods
            and all(static_method(member) for member in methods)
            and sum(map(is_public, methods)) == 1
            and namespace_only(parsed, node, name)
        )
        if eligible:
            findings.append(Finding(parsed.path, line_of(node), CHECK_ID, Severity.WARNING, MESSAGE.format(name=name)))
    return findings
