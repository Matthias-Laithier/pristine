import re
from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.clients.literals import string_content
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text

MAJOR_VERSION = re.compile(r"v\d+")
IDENTIFIER = re.compile(r"[A-Za-z_]\w*")


def called_packages(source: Node | ParsedFile) -> set[str]:
    functions = (node.child_by_field_name("function") for node in all_nodes(source) if node.type == "call_expression")
    selectors = (function for function in functions if function is not None and function.type == "selector_expression")
    operands = (selector.child_by_field_name("operand") for selector in selectors)
    return {node_text(operand) or "" for operand in operands if operand is not None and operand.type == "identifier"}


def package_name(spec: Node, path: str) -> str | None:
    alias = node_text(spec.child_by_field_name("name"))
    if alias is not None:
        return alias if IDENTIFIER.fullmatch(alias) and alias != "_" else None
    segments = path.split("/")
    last = segments[-2] if len(segments) > 1 and MAJOR_VERSION.fullmatch(segments[-1]) else segments[-1]
    return last if IDENTIFIER.fullmatch(last) else None


def go_import_modules(source: Node | ParsedFile) -> Iterator[tuple[str, int]]:
    called = called_packages(source)
    for spec in (node for node in all_nodes(source) if node.type == "import_spec"):
        path = string_content(spec.child_by_field_name("path"))
        name = None if path is None else package_name(spec, path)
        if path is not None and name in called:
            yield path, line_of(spec)
