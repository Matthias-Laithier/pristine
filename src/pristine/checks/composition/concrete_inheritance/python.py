import re
from collections import Counter
from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.checks.definitions import FileCheck
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.syntax.parsing import ParsedFile, all_nodes, is_docstring, line_of, node_text, unwrapped
from pristine.syntax.python_scopes import CLASS_KIND, FUNCTION_KIND

CHECK_ID = "DEP-1"
PLAIN_BASES = frozenset({"object"})
ABSTRACT_MARKER = "abstractmethod"
EXTENSION_NAME = re.compile(r"_|.*(Base|Mixin|Abstract|Interface|Protocol|Default)")
DUNDER_NAME = re.compile(r"__\w+__")
STUB_KINDS = frozenset({"pass_statement", "ellipsis", "raise_statement"})
EMPTY_VALUES = frozenset({"none", "list", "dictionary", "tuple", "true", "false", "string", "integer"})
MIN_BEHAVIOR_STATEMENTS = 2
MESSAGE = (
    "class '{name}' subclasses concrete '{base}' and overrides '{method}'; "
    "wrap the base in a new class that delegates to it"
)


def class_name(node: Node) -> str:
    return node_text(node.child_by_field_name("name")) or ""


def base_names(node: Node) -> list[str]:
    bases = node.child_by_field_name("superclasses")
    return [] if bases is None else [node_text(base) or "" for base in bases.named_children]


def methods(node: Node) -> dict[str, Node]:
    body = node.child_by_field_name("body")
    members = [] if body is None else [unwrapped(member) for member in body.named_children]
    named = {node_text(member.child_by_field_name("name")) or "": member for member in members}
    return {
        name: member
        for name, member in named.items()
        if member.type == FUNCTION_KIND and not DUNDER_NAME.fullmatch(name)
    }


def statements(method: Node) -> list[Node]:
    body = method.child_by_field_name("body")
    return [] if body is None else [node for node in body.named_children if not is_docstring(node)]


def is_stub(method: Node) -> bool:
    body = statements(method)
    if len(body) != 1:
        return not body
    statement = body[0]
    inner = statement.named_children[0] if statement.named_children else None
    is_constant_return = statement.type == "return_statement" and (inner is None or inner.type in EMPTY_VALUES)
    is_bare_value = statement.type == "expression_statement" and inner is not None and inner.type in STUB_KINDS
    return statement.type in STUB_KINDS or is_constant_return or is_bare_value


def is_concrete_leaf(node: Node) -> bool:
    has_plain_header = set(base_names(node)) <= PLAIN_BASES and node.child_by_field_name("type_parameters") is None
    decorators = (found for found in all_nodes(node) if found.type == "decorator")
    is_abstract = any(ABSTRACT_MARKER in (node_text(decorator) or "") for decorator in decorators)
    has_stub = any(is_stub(method) for method in methods(node).values())
    is_wrapped = node.parent is not None and node.parent.type == "decorated_definition"
    named_for_extension = EXTENSION_NAME.match(class_name(node)) is not None
    return has_plain_header and not (is_abstract or has_stub or is_wrapped or named_for_extension)


def overridden(node: Node, base: Node) -> str | None:
    inherited = methods(base)
    replaced = (name for name in sorted(methods(node).keys() & inherited.keys()))
    return next((name for name in replaced if len(statements(inherited[name])) >= MIN_BEHAVIOR_STATEMENTS), None)


def check_concrete_inheritance(parsed: ParsedFile) -> list[Finding]:
    if parsed.language != "python" or is_test_path(PurePath(parsed.path)):
        return []
    definitions = [unwrapped(node) for node in parsed.root.named_children]
    classes = {class_name(node): node for node in definitions if node.type == CLASS_KIND}
    subclass_counts = Counter(base for node in classes.values() for base in base_names(node))
    findings = []
    for name, node in classes.items():
        bases = base_names(node)
        base = bases[0] if len(bases) == 1 else ""
        is_sole_variant = base in classes and subclass_counts[base] == 1
        method = overridden(node, classes[base]) if is_sole_variant and is_concrete_leaf(classes[base]) else None
        if method is not None:
            message = MESSAGE.format(name=name, base=base, method=method)
            findings.append(Finding(parsed.path, line_of(node), CHECK_ID, Severity.WARNING, message))
    return findings


CHECK = FileCheck(
    check_id=CHECK_ID,
    title="Concrete Inheritance Overrides",
    summary=(
        "Python classes outside tests whose only base is a plain concrete class of the same module, one with no "
        "bases, decorators, abstract or stub methods, extension name, or other subclass there, and that override "
        "one of its methods that holds at least two statements."
    ),
    run=check_concrete_inheritance,
)
