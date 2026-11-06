import re

from tree_sitter import Node

from pristine.checks.registry import FileCheck, register_file_check
from pristine.reports.findings import Finding, Severity
from pristine.syntax.calls import callee_of
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text
from pristine.syntax.python_tests import is_python_test_module

RULE_ID = "TST-1"
PRIVATE_NAME = re.compile(r"_[A-Za-z0-9]\w*(?<!_)")
OWN_RECEIVERS = frozenset({"self", "cls", "super()"})
DOUBLE_PREFIXES = ("mock", "fake")
EFFECTIVELY_PUBLIC = frozenset({"_meta", "_asdict", "_replace", "_fields", "_make", "_field_defaults"})
PUBLIC_MODULE_PRIVATES = frozenset({"sys._getframe", "os._exit"})
METHOD_KIND = "function_definition"
PATCH_CALLEES = re.compile(r"(\w+\.)*(patch(\.object|\.multiple|\.dict)?|setattr|delattr|spy)")


def receiver_name(receiver: Node) -> str:
    name = receiver.child_by_field_name("attribute") if receiver.type == "attribute" else receiver
    return node_text(name) or ""


def is_patch_target(access: Node) -> bool:
    holder = access.parent
    while holder is not None and holder.type != "call":
        holder = holder.parent
    return holder is not None and PATCH_CALLEES.fullmatch(callee_of(holder)) is not None


def is_private_access(node: Node) -> bool:
    name = node_text(node.child_by_field_name("attribute")) or ""
    return node.type == "attribute" and PRIVATE_NAME.fullmatch(name) is not None


def own_members(root: Node) -> set[str]:
    members = {
        node_text(node.child_by_field_name("name")) or "" for node in all_nodes(root) if node.type == METHOD_KIND
    }
    accesses = (node for node in all_nodes(root) if node.type == "attribute")
    receivers = ((node, node.child_by_field_name("object")) for node in accesses)
    own = (node for node, receiver in receivers if receiver is not None and node_text(receiver) in OWN_RECEIVERS)
    return members | {node_text(node.child_by_field_name("attribute")) or "" for node in own}


def is_exempt(access: Node, receiver: Node, exempt_names: frozenset[str]) -> bool:
    receiver_text = receiver_name(receiver)
    if receiver_text in OWN_RECEIVERS or receiver_text.lower().startswith(DOUBLE_PREFIXES):
        return True
    inner = receiver.child_by_field_name("object")
    if is_private_access(receiver) and inner is not None and not is_exempt(receiver, inner, exempt_names):
        return True
    name = node_text(access.child_by_field_name("attribute")) or ""
    return name in exempt_names or f"{node_text(receiver)}.{name}" in PUBLIC_MODULE_PRIVATES or is_patch_target(access)


def private_accesses(root: Node) -> list[Node]:
    exempt_names = EFFECTIVELY_PUBLIC | own_members(root)
    accesses = [node for node in all_nodes(root) if is_private_access(node)]
    return [
        node
        for node in accesses
        if (receiver := node.child_by_field_name("object")) is not None and not is_exempt(node, receiver, exempt_names)
    ]


def check_private_access_in_tests(parsed: ParsedFile) -> list[Finding]:
    if not is_python_test_module(parsed):
        return []
    return [
        Finding(
            parsed.path,
            line_of(node),
            RULE_ID,
            Severity.WARNING,
            f"test reaches into private attribute '{node_text(node)}'; "
            "assert on the public outcome instead: return values, persisted state, emitted events, or calls to fakes",
        )
        for node in private_accesses(parsed.root)
    ]


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Python test modules (test paths that define test functions or classes, and conftest.py) reading or "
            "writing a single-underscore private attribute of an object other than self or cls. Mock and monkeypatch targets, mock* and fake* variables, and framework privates such as "
            "_meta, _asdict, _replace, _fields, sys._getframe, and os._exit are exempt."
        ),
        run=check_private_access_in_tests,
    )
)
