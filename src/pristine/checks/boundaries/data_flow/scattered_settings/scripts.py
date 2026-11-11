from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.clients.literals import string_content
from pristine.clients.script_calls import enclosing_function, is_shadowed
from pristine.files.path_roles import is_test_path
from pristine.syntax.parsing import ParsedFile, all_nodes, function_name, node_text

PUBLIC_PREFIXES = ("NEXT_PUBLIC_", "REACT_APP_", "VITE_", "PUBLIC_")
STARTUP_NAMES = frozenset({"main", "bootstrap", "startup", "configure", "loadSettings", "loadConfig", "getConfig"})
STARTUP_FILES = frozenset(
    {"main", "cli", "config", "settings", "next.config", "vite.config", "nuxt.config", "svelte.config"}
)


def is_startup(parsed: ParsedFile) -> bool:
    path = PurePath(parsed.path)
    return is_test_path(path) or path.stem in STARTUP_FILES or parsed.text.startswith("#!")


def environment_key(node: Node) -> str | None:
    if node.type not in {"member_expression", "subscript_expression"}:
        return None
    owner = node_text(node.child_by_field_name("object"))
    if owner != "process.env" or is_shadowed(node, "process"):
        return None
    key = node.child_by_field_name("property") or node.child_by_field_name("index")
    name = node_text(key) if node.type == "member_expression" else string_content(key)
    parent = node.parent
    is_write = parent is not None and (
        (
            parent.type in {"assignment_expression", "augmented_assignment_expression"}
            and parent.child_by_field_name("left") == node
        )
        or parent.type == "update_expression"
        or (parent.type == "unary_expression" and node_text(parent.child_by_field_name("operator")) == "delete")
    )
    return None if is_write else name


def environment_reads(parsed: ParsedFile) -> list[tuple[Node, str]]:
    if is_startup(parsed):
        return []
    reads = []
    for node in all_nodes(parsed):
        function = enclosing_function(node)
        key = environment_key(node)
        if (
            function is not None
            and function_name(function) not in STARTUP_NAMES
            and key is not None
            and not key.startswith(PUBLIC_PREFIXES)
            and key not in {"NODE_ENV", "NODE_OPTIONS"}
        ):
            reads.append((node, key))
    return reads
