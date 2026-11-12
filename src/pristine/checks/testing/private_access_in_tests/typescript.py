import re

lazy from tree_sitter import Node

from pristine.checks.testing.script_scopes import ScriptResolution, parents, test_callbacks
from pristine.syntax.parsing import ParsedFile, all_nodes, node_text

PRIVATE = re.compile(r"_[A-Za-z0-9]\w*(?<!_)")
PUBLIC = frozenset({"_meta", "_asdict", "_replace", "_fields", "_make", "_field_defaults"})
SPIES = frozenset({"vi.spyOn", "jest.spyOn", "vitest.vi.spyOn", "@jest/globals.jest.spyOn"})


def private_member(node: Node) -> bool:
    name = node_text(node.child_by_field_name("property")) or ""
    return node.type == "member_expression" and PRIVATE.fullmatch(name) is not None


def exempt(node: Node, resolution: ScriptResolution) -> bool:
    receiver = node.child_by_field_name("object")
    name = node_text(node.child_by_field_name("property")) or ""
    if receiver is None or name in PUBLIC:
        return True
    head = receiver
    while head.type == "member_expression":
        inner = head.child_by_field_name("object")
        if inner is None:
            break
        head = inner
    if node_text(head) == "this" or (node_text(head) or "").lower().startswith(("mock", "fake")):
        return True
    if private_member(receiver) and not exempt(receiver, resolution):
        return True
    call = next((holder for holder in parents(node) if holder.type == "call_expression"), None)
    arguments = None if call is None else call.child_by_field_name("arguments")
    return (
        call is not None
        and resolution.qualified(call) in SPIES
        and arguments is not None
        and arguments.named_child_count > 0
        and node in all_nodes(arguments.named_children[0])
    )


def typescript_private_accesses(parsed: ParsedFile) -> list[Node]:
    resolution = ScriptResolution()
    return [
        node
        for test in test_callbacks(parsed, resolution)
        for node in all_nodes(test)
        if private_member(node) and not exempt(node, resolution)
    ]
