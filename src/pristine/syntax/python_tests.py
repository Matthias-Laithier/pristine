from pathlib import PurePath

from tree_sitter import Node

from pristine.files.path_roles import PYTEST_CONFTEST, is_test_path
from pristine.syntax.parsing import ParsedFile, all_nodes, node_text

TEST_PREFIXES = {"function_definition": "test", "class_definition": "Test"}


def is_test_definition(node: Node) -> bool:
    prefix = TEST_PREFIXES.get(node.type)
    name = node_text(node.child_by_field_name("name")) or ""
    return prefix is not None and name.startswith(prefix)


def defines_tests(root: Node) -> bool:
    return any(is_test_definition(node) for node in all_nodes(root))


def is_python_test_module(parsed: ParsedFile) -> bool:
    path = PurePath(parsed.path)
    if parsed.language != "python" or not is_test_path(path):
        return False
    return path.name == PYTEST_CONFTEST or defines_tests(parsed.root)
