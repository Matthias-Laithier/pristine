from collections.abc import Iterator
from dataclasses import dataclass

from tree_sitter import Node, Tree

from pristine.services.grammars import parser_for
from pristine.syntax_kinds import (
    COMMENT_KINDS,
    DOCSTRING_CONTAINERS,
    DOCSTRING_LANGUAGES,
    DOCUMENTATION_PREFIXES,
    FUNCTION_KINDS,
)

MODULE_WRAPPER_FIELDS = {"export_statement": "declaration", "decorated_definition": "definition"}
MODULE_EXPRESSION_KIND = "expression_statement"


@dataclass(frozen=True)
class FunctionSpan:
    name: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class CommentText:
    line: int
    text: str
    is_documentation: bool


@dataclass(frozen=True)
class ParsedFile:
    path: str
    language: str
    text: str
    tree: Tree
    functions: list[FunctionSpan]
    comments: list[CommentText]

    @property
    def root(self) -> Node:
        return self.tree.root_node


def line_of(node: Node) -> int:
    return node.start_point.row + 1


def all_nodes(root: Node) -> Iterator[Node]:
    pending = [root]
    while pending:
        node = pending.pop()
        yield node
        pending.extend(reversed(node.named_children))


def unwrapped(node: Node) -> Node:
    inner = node.child_by_field_name(MODULE_WRAPPER_FIELDS.get(node.type, ""))
    return node if inner is None else unwrapped(inner)


def module_statements(root: Node) -> Iterator[Node]:
    for statement in map(unwrapped, root.named_children):
        yield from statement.named_children if statement.type == MODULE_EXPRESSION_KIND else [statement]


def node_text(node: Node | None) -> str | None:
    if node is None or node.text is None:
        return None
    return node.text.decode(errors="replace")


def function_name(node: Node) -> str:
    holder = node.parent
    own_name = node_text(node.child_by_field_name("name"))
    holder_name = None if holder is None else node_text(holder.child_by_field_name("name"))
    return own_name or holder_name or "<anonymous>"


def is_docstring(node: Node) -> bool:
    parent = node.parent
    if parent is None or parent.type not in DOCSTRING_CONTAINERS or parent.named_children[0] != node:
        return False
    if node.type == "string":
        return True
    return node.type == "expression_statement" and [child.type for child in node.named_children] == ["string"]


def comment_text(node: Node) -> CommentText:
    text = node_text(node) or ""
    is_documentation = node.type not in COMMENT_KINDS or text.lstrip().startswith(DOCUMENTATION_PREFIXES)
    return CommentText(line_of(node), text, is_documentation)


def parse_file(path: str, text: str, language: str) -> ParsedFile:
    tree = parser_for(language).parse(text.encode())
    nodes = list(all_nodes(tree.root_node))
    functions = [
        FunctionSpan(function_name(node), line_of(node), node.end_point.row + 1)
        for node in nodes
        if node.type in FUNCTION_KINDS
    ]
    has_docstrings = language in DOCSTRING_LANGUAGES
    comments = [
        comment_text(node) for node in nodes if node.type in COMMENT_KINDS or (has_docstrings and is_docstring(node))
    ]
    return ParsedFile(path, language, text, tree, functions, sorted(comments, key=lambda comment: comment.line))
