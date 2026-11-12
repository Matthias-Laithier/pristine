from collections.abc import Iterator
from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding, Severity
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.calls import calls_of
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text

CHECK_ID = "STR-11"
PYTHON = "python"
LOOKUP_NAME_POSITIONS = {
    "getattr": 1,
    "setattr": 1,
    "hasattr": 1,
    "delattr": 1,
    "importlib.import_module": 0,
    "import_module": 0,
    "__import__": 0,
}
BUILT_STRING_KINDS = frozenset({"binary_operator", "binary_expression", "template_string"})
ENTRY_POINT_STEMS = frozenset({"index", "__init__"})
LOOKUP_FIX = "name the target literally, or map each value to its target in a dict literal (STR-8)"
WILDCARD_FIX = "import each name you use from the module that defines it"
DATA_MODULE_SUFFIX = ".json"
REEXPORT_FIX = "import from the defining module; only a package entry point such as index.ts re-exports"


def is_built_string(node: Node) -> bool:
    if node.type == "string":
        return any(child.type == "interpolation" for child in node.named_children)
    if node.type == "template_string":
        return any(child.type == "template_substitution" for child in node.named_children)
    is_text = any(part.type in {"string", "template_string"} for part in node.named_children)
    is_concatenation = any(not child.is_named and child.type == "+" for child in node.children)
    return node.type in BUILT_STRING_KINDS and is_concatenation and is_text


def literal_fragments(node: Node) -> list[str]:
    kinds = {"string_content", "string_fragment"}
    return [node_text(child) or "" for child in all_nodes(node) if child.type in kinds]


def loads_data(callee: str, name: Node) -> bool:
    return callee == "import" and any(DATA_MODULE_SUFFIX in fragment for fragment in literal_fragments(name))


def dynamic_lookups(parsed: ParsedFile, call_kind: str) -> Iterator[Finding]:
    for node, callee, arguments in calls_of(parsed, call_kind):
        position = LOOKUP_NAME_POSITIONS.get(callee, 0 if callee == "import" else None)
        if position is None or len(arguments) <= position or not is_built_string(arguments[position]):
            continue
        if loads_data(callee, arguments[position]):
            continue
        message = f"'{callee}' looks up a name built at runtime, which no search can find; {LOOKUP_FIX}"
        yield Finding(parsed.path, line_of(node), CHECK_ID, Severity.WARNING, message)


def python_wildcards(parsed: ParsedFile) -> Iterator[Finding]:
    for node in parsed.nodes_of("wildcard_import"):
        yield Finding(parsed.path, line_of(node), CHECK_ID, Severity.ERROR, f"wildcard import; {WILDCARD_FIX}")


def script_reexports(parsed: ParsedFile) -> Iterator[Finding]:
    if PurePath(parsed.path).name.split(".")[0] in ENTRY_POINT_STEMS:
        return
    for node in parsed.root.named_children:
        if node.type == "export_statement" and node.child_by_field_name("source") is not None:
            yield Finding(parsed.path, line_of(node), CHECK_ID, Severity.WARNING, f"re-export; {REEXPORT_FIX}")


def check_greppable_names(parsed: ParsedFile) -> list[Finding]:
    if parsed.language == PYTHON:
        return [*dynamic_lookups(parsed, "call"), *python_wildcards(parsed)]
    if parsed.language in SCRIPT_LANGUAGES:
        return [*dynamic_lookups(parsed, "call_expression"), *script_reexports(parsed)]
    return []


CHECK = FileCheck(
    check_id=CHECK_ID,
    title="Dynamic Names and Wildcard Imports",
    summary=(
        "Python and TypeScript: attribute and module lookups by a name built from a string template "
        "or concatenation, wildcard imports, and TypeScript re-exports outside a "
        "package entry point."
    ),
    run=check_greppable_names,
)
