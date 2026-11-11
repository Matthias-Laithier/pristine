import re
from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.checks.definitions import FileCheck
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.syntax.parsing import ParsedFile, all_nodes, is_docstring, line_of, node_text

RULE_ID = "CO-5"
PLAIN_BASES = frozenset({"object"})
STATIC_DECORATOR = "staticmethod"
CLASS_DECORATOR = "classmethod"
METHOD_DECORATORS = frozenset({STATIC_DECORATOR, CLASS_DECORATOR})
METHOD_KIND = "function_definition"
PRIVATE_PREFIX = "_"
EXPORT_LIST = "__all__"
NEUTRAL_MEMBER_KINDS = frozenset({"pass_statement", "comment"})
STUB_STATEMENT_KINDS = frozenset({"pass_statement", "raise_statement", "comment", "ellipsis"})
DUNDER_NAME = re.compile(r"__\w+__")
TEST_CLASS_NAME = re.compile(r"Test\w*")
MESSAGE = "class '{name}' only groups functions that need no instance; make them module-level functions"


def base_names(source: Node | ParsedFile) -> set[str]:
    classes = [node for node in all_nodes(source) if node.type == "class_definition"]
    bases = [node.child_by_field_name("superclasses") for node in classes]
    names = [node_text(base) or "" for holder in bases if holder is not None for base in holder.named_children]
    return {name.rsplit(".", 1)[-1] for name in names}


def has_plain_header(node: Node) -> bool:
    bases = node.child_by_field_name("superclasses")
    if node.child_by_field_name("type_parameters") is not None:
        return False
    return bases is None or {node_text(base) for base in bases.named_children} <= PLAIN_BASES


def decorator_names(node: Node) -> set[str | None]:
    return {node_text(child.named_children[0]) for child in node.named_children if child.type == "decorator"}


def receiver_name(method: Node) -> str | None:
    parameters = method.child_by_field_name("parameters")
    first = parameters.named_children[0] if parameters is not None and parameters.named_children else None
    if first is not None and first.type == "typed_parameter":
        first = first.named_children[0]
    return node_text(first) if first is not None and first.type == "identifier" else None


def uses_receiver(method: Node, receiver: str) -> bool:
    body = method.child_by_field_name("body")
    names = [] if body is None else all_nodes(body)
    return any(node.type == "identifier" and node_text(node) == receiver for node in names)


def is_free_method(method: Node, decorators: set[str | None]) -> bool:
    body = method.child_by_field_name("body")
    if DUNDER_NAME.fullmatch(node_text(method.child_by_field_name("name")) or "") or body is None:
        return False
    if all(statement.type in STUB_STATEMENT_KINDS or is_docstring(statement) for statement in body.named_children):
        return False
    if STATIC_DECORATOR in decorators:
        return True
    receiver = receiver_name(method)
    return CLASS_DECORATOR in decorators and receiver is not None and not uses_receiver(method, receiver)


def is_free_member(member: Node) -> bool:
    if member.type == METHOD_KIND:
        return is_free_method(member, set())
    if member.type == "decorated_definition":
        method = member.child_by_field_name("definition")
        decorators = decorator_names(member)
        is_method = method is not None and method.type == METHOD_KIND
        return is_method and decorators <= METHOD_DECORATORS and is_free_method(method, decorators)
    return member.type in NEUTRAL_MEMBER_KINDS or is_docstring(member)


def method_names(members: list[Node]) -> list[str]:
    methods = [member.child_by_field_name("definition") or member for member in members]
    return [node_text(method.child_by_field_name("name")) or "" for method in methods if method.type == METHOD_KIND]


def is_stateless(node: Node) -> bool:
    body = node.child_by_field_name("body")
    members = [] if body is None else body.named_children
    public = [name for name in method_names(members) if not name.startswith(PRIVATE_PREFIX)]
    has_helpers = len(public) < len(method_names(members))
    is_single_entry = len(public) <= 1 and len(method_names(members)) > 0
    is_plain = has_plain_header(node) and all(is_free_member(member) for member in members)
    return is_plain and (has_helpers or is_single_entry)


def is_namespace_access(name: Node) -> bool:
    holder = name.parent
    return holder is not None and holder.type == "attribute" and holder.child_by_field_name("object") == name


def is_export_list(statement: Node) -> bool:
    return (node_text(statement) or "").startswith(EXPORT_LIST)


def is_used_as_namespace(root: Node, node: Node, name: str) -> bool:
    statements = [child for child in root.named_children if child != node and not is_export_list(child)]
    outside = [found for child in statements for found in all_nodes(child)]
    references = [found for found in outside if found.type == "identifier" and node_text(found) == name]
    is_named_in_text = any(found.type == "string" and name in (node_text(found) or "") for found in outside)
    return not is_named_in_text and all(is_namespace_access(found) for found in references)


def is_exempt(name: str, extended: set[str], *, in_tests: bool) -> bool:
    is_test_class = in_tests and TEST_CLASS_NAME.fullmatch(name) is not None
    return is_test_class or name in extended


def check_stateless_classes(parsed: ParsedFile) -> list[Finding]:
    if parsed.language != "python":
        return []
    extended = base_names(parsed)
    in_tests = is_test_path(PurePath(parsed.path))
    findings = []
    for node in parsed.root.named_children:
        name = node_text(node.child_by_field_name("name")) or ""
        if (
            node.type == "class_definition"
            and not is_exempt(name, extended, in_tests=in_tests)
            and is_stateless(node)
            and is_used_as_namespace(parsed.root, node, name)
        ):
            message = MESSAGE.format(name=name)
            findings.append(Finding(parsed.path, line_of(node), RULE_ID, Severity.WARNING, message))
    return findings


CHECK = FileCheck(
    rule_id=RULE_ID,
    title="Functions Where Possible, Classes Where Needed",
    summary=(
        "Python module-level classes that only group static or class methods, with one public method or "
        "private helpers, no bases, decorators, attributes, or instances."
    ),
    run=check_stateless_classes,
)
