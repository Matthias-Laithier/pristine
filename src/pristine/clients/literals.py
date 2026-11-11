lazy from tree_sitter import Node

from pristine.syntax.parsing import node_text

STRING_LITERAL_KINDS = frozenset({"string"})


def string_content(node: Node | None) -> str | None:
    if node is None or node.type not in STRING_LITERAL_KINDS:
        return None
    return (node_text(node) or "").strip("\"'`")
