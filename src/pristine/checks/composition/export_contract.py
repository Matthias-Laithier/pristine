from collections.abc import Callable, Iterator
from pathlib import Path

lazy from tree_sitter import Node

from pristine.checks.definitions import FileCheck
from pristine.checks.prefilters import requiring
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text, typed_nodes

CHECK_ID = "DEP-4"
EXPORT_LIST = "__all__"
PACKAGE_INIT = "__init__.py"
SCRIPT_INDEX_STEM = "index"
DYNAMIC_NAMESPACE_MARKERS = ("globals()", "sys.modules[", "def __getattr__", "lazy.attach")
IMPORT_KINDS = frozenset({"import_from_statement", "import_statement", "future_import_statement"})
BINDING_FIELDS = dict.fromkeys(("assignment", "augmented_assignment", "for_statement", "type_alias_statement"), "left")
BINDING_FIELDS |= dict.fromkeys(
    ("function_definition", "class_definition", "import_from_statement", "import_statement", "named_expression"), "name"
)
BINDING_KINDS = frozenset({"as_pattern_target", "global_statement"})
EXPORT_SEQUENCE_KINDS = frozenset({"list", "tuple"})
PLAIN_STRING_SHAPE = ["string_start", "string_content", "string_end"]
STAR_EXPORT_EXCLUSIONS = frozenset({"export_clause", "namespace_export"})


def identifiers(node: Node) -> set[str]:
    return {node_text(child) or "" for child in all_nodes(node) if child.type == "identifier"}


def binding_targets(node: Node) -> list[Node]:
    if node.type in BINDING_KINDS:
        return [node]
    return node.children_by_field_name(BINDING_FIELDS.get(node.type, ""))


def defined_names(source: Node | ParsedFile) -> set[str]:
    return {
        name
        for node in typed_nodes(source, *BINDING_KINDS, *BINDING_FIELDS)
        for target in binding_targets(node)
        for name in identifiers(target)
    }


def export_sequence(node: Node) -> list[Node]:
    is_export_binding = node.type in BINDING_FIELDS and node_text(node.child_by_field_name("left")) == EXPORT_LIST
    sequence = node.child_by_field_name("right") if is_export_binding else None
    if sequence is None or sequence.type not in EXPORT_SEQUENCE_KINDS:
        return []
    return [entry for entry in sequence.named_children if [part.type for part in entry.children] == PLAIN_STRING_SHAPE]


def export_entries(source: Node | ParsedFile) -> list[tuple[Node, str]]:
    return [
        (entry, node_text(entry.children[1]) or "")
        for node in typed_nodes(source, *BINDING_FIELDS)
        for entry in export_sequence(node)
    ]


def export_list_findings(parsed: ParsedFile) -> Iterator[Finding]:
    is_dynamic = any(marker in parsed.text for marker in DYNAMIC_NAMESPACE_MARKERS)
    is_open = is_dynamic or bool(parsed.nodes_of("wildcard_import"))
    defined = defined_names(parsed)
    for entry, name in export_entries(parsed):
        if not is_open and name not in defined:
            message = f"{EXPORT_LIST} lists '{name}', which the module neither defines nor imports; remove or fix it"
            yield Finding(parsed.path, line_of(entry), CHECK_ID, Severity.ERROR, message)
        elif name.startswith("_") and not name.endswith("__"):
            message = f"{EXPORT_LIST} lists the private name '{name}'; drop it or make it public deliberately"
            yield Finding(parsed.path, line_of(entry), CHECK_ID, Severity.WARNING, message)


def imports_names_from_submodule(statement: Node, package: Path) -> bool:
    source = statement.child_by_field_name("module_name")
    if source is None or statement.type != "import_from_statement":
        return False
    if source.type == "relative_import":
        return any(child.type == "dotted_name" for child in source.named_children)
    module_parts = (node_text(source) or "").split(".")
    return module_parts[0] in package.parts and module_parts[-1] != package.name


def reexported_names(statement: Node, used: set[str]) -> list[str]:
    names = []
    for imported in statement.children_by_field_name("name"):
        original = node_text(imported.child_by_field_name("name")) or node_text(imported)
        bound = node_text(imported.child_by_field_name("alias")) or original
        if bound != original or imported.type != "aliased_import":
            names.append(bound or "")
    has_wildcard = any(child.type == "wildcard_import" for child in statement.named_children)
    return [name for name in names if name not in used] + (["*"] if has_wildcard else [])


def package_reexport_findings(parsed: ParsedFile) -> Iterator[Finding]:
    path = Path(parsed.path).absolute()
    if path.name != PACKAGE_INIT or EXPORT_LIST in defined_names(parsed):
        return
    statements = parsed.root.named_children
    used = set().union(*(identifiers(node) for node in statements if node.type not in IMPORT_KINDS))
    reexports = [
        (node, reexported_names(node, used)) for node in statements if imports_names_from_submodule(node, path.parent)
    ]
    for statement, names in reexports:
        if names:
            message = f"package re-exports {', '.join(names)} without {EXPORT_LIST}; declare the public names in it"
            yield Finding(parsed.path, line_of(statement), CHECK_ID, Severity.WARNING, message)
            return


def is_relative_star_export(statement: Node) -> bool:
    source = node_text(statement.child_by_field_name("source")) or ""
    tokens = {child.type for child in statement.children}
    is_star = statement.type == "export_statement" and "*" in tokens and not tokens & STAR_EXPORT_EXCLUSIONS
    return is_star and source.strip("'\"").startswith(".")


def script_findings(parsed: ParsedFile) -> Iterator[Finding]:
    if Path(parsed.path).stem != SCRIPT_INDEX_STEM:
        return
    for statement in filter(is_relative_star_export, parsed.root.named_children):
        source = node_text(statement.child_by_field_name("source"))
        message = f"index re-exports every name of {source}; export the public names explicitly"
        yield Finding(parsed.path, line_of(statement), CHECK_ID, Severity.WARNING, message)


LANGUAGE_CHECKS: dict[str, tuple[Callable[[ParsedFile], Iterator[Finding]], ...]] = {
    "python": (package_reexport_findings, export_list_findings),
} | dict.fromkeys(SCRIPT_LANGUAGES, (script_findings,))


def may_break_contract(parsed: ParsedFile) -> bool:
    path = Path(parsed.path)
    if parsed.language == "python":
        return path.name == PACKAGE_INIT or EXPORT_LIST in parsed.text
    return path.stem == SCRIPT_INDEX_STEM


def check_export_contract(parsed: ParsedFile) -> list[Finding]:
    if is_test_path(Path(parsed.path)):
        return []
    return [finding for check in LANGUAGE_CHECKS.get(parsed.language, ()) for finding in check(parsed)]


CHECK = FileCheck(
    check_id=CHECK_ID,
    title="Export Contracts",
    summary=(
        "Python: a package __init__.py that re-exports names without __all__, and __all__ entries that are "
        "undefined or private. JS/TS: export * from a relative module in an index file. Tests are exempt."
    ),
    run=requiring(may_break_contract, check_export_contract),
)
