from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.checks.boundaries.data_flow.injection.constructed import Injection
from pristine.checks.boundaries.data_flow.injection.scripts.values import is_built, string_value
from pristine.syntax.calls import calls_of
from pristine.syntax.parsing import ParsedFile, node_text

CHILD_PROCESS_MODULES = frozenset({"child_process", "node:child_process"})
IMPORT_OR_DECLARATOR_KINDS = frozenset({"import_statement", "variable_declarator"})
MODULE = "*"
SHELL_EXECUTORS = frozenset({"exec", "execSync"})
PROMISIFIERS = frozenset({"promisify", "util.promisify"})
REQUIRE = "require"
SHELL_FIX = "pass an argument list to execFile or spawn without a shell"


def first_argument(call: Node | None) -> Node | None:
    arguments = None if call is None else call.child_by_field_name("arguments")
    return arguments.named_children[0] if arguments is not None and arguments.named_children else None


def specifier_binding(specifier: Node) -> tuple[str, str]:
    name = node_text(specifier.child_by_field_name("name")) or ""
    return node_text(specifier.child_by_field_name("alias")) or name, name


def clause_bindings(clause: Node) -> Iterator[tuple[str, str]]:
    for child in clause.named_children:
        if child.type in ("identifier", "namespace_import"):
            yield node_text(child.named_children[0] if child.named_children else child) or "", MODULE
        yield from map(specifier_binding, child.named_children if child.type == "named_imports" else [])


def pattern_bindings(pattern: Node) -> Iterator[tuple[str, str]]:
    if pattern.type == "identifier":
        yield node_text(pattern) or "", MODULE
    for child in pattern.named_children if pattern.type == "object_pattern" else []:
        local = child.child_by_field_name("value") or child
        yield node_text(local) or "", node_text(child.child_by_field_name("key") or child) or ""


def import_bindings(node: Node) -> Iterator[tuple[str, str]]:
    value = node.child_by_field_name("value")
    is_require = value is not None and value.type == "call_expression"
    if is_require and node_text(value.child_by_field_name("function")) == REQUIRE:
        source = string_value(first_argument(value))
        yield from pattern_bindings(node.child_by_field_name("name") or node) if source in CHILD_PROCESS_MODULES else ()
    clause = next((child for child in node.named_children if child.type == "import_clause"), None)
    if node.type == "import_statement" and clause is not None:
        source = string_value(node.child_by_field_name("source"))
        yield from clause_bindings(clause) if source in CHILD_PROCESS_MODULES else ()


def promisified(node: Node, bindings: dict[str, str]) -> str | None:
    value = node.child_by_field_name("value")
    if value is None or value.type != "call_expression":
        return None
    is_promisify = node_text(value.child_by_field_name("function")) in PROMISIFIERS
    return bindings.get(node_text(first_argument(value)) or "") if is_promisify else None


def child_process_bindings(parsed: ParsedFile) -> dict[str, str]:
    nodes = parsed.nodes_of(*IMPORT_OR_DECLARATOR_KINDS)
    bindings = dict(binding for node in nodes for binding in import_bindings(node))
    declarators = [node for node in nodes if node.type == "variable_declarator"]
    promises = {node_text(node.child_by_field_name("name")) or "": promisified(node, bindings) for node in declarators}
    return bindings | {name: imported for name, imported in promises.items() if imported is not None}


def runs_shell(callee: str, bindings: dict[str, str]) -> bool:
    receiver, _, member = callee.rpartition(".")
    if receiver:
        return bindings.get(receiver) == MODULE and member in SHELL_EXECUTORS
    return bindings.get(callee) in SHELL_EXECUTORS


def scan_processes(parsed: ParsedFile) -> Iterator[Injection]:
    bindings = child_process_bindings(parsed)
    if not bindings:
        return
    for node, callee, arguments in calls_of(parsed, "call_expression"):
        if arguments and runs_shell(callee, bindings) and is_built(arguments[0]):
            yield Injection(node, f"'{callee}' runs a shell command built from non-literal values; {SHELL_FIX}")
