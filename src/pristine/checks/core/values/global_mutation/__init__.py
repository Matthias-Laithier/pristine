from tree_sitter import Node

from pristine.checks.core.values.global_mutation.module_globals import binds_locally, module_globals
from pristine.checks.core.values.global_mutation.writes import Mutation, find_mutation
from pristine.checks.registry import FileCheck, register_file_check
from pristine.reports.findings import Finding, Severity
from pristine.syntax.parsing import ParsedFile, all_nodes, function_name, line_of, node_text
from pristine.syntax.syntax_kinds import CALL_KINDS, FUNCTION_KINDS

RULE_ID = "CR-7"
SCOPE_KINDS = FUNCTION_KINDS | {"generator_function"}
ENCAPSULATED_NAME_PARTS = ("cache", "memo")
OWNING_FUNCTION_PARTS = ("regist", "subscri", "listen")
TEST_HOOKS = frozenset({"beforeEach", "beforeAll", "afterEach", "afterAll"})
FIXTURE_MARKER = "fixture"
MEMO_READ_METHODS = ("get", "has")
LAZY_OPERATORS = frozenset({"??=", "||="})
FIX_HINT = "give the state an owner passed to its consumers and keep module-level values as read-only config"


def enclosing_scopes(node: Node) -> list[Node]:
    scopes: list[Node] = []
    parent = node.parent
    while parent is not None:
        scopes.extend([parent] if parent.type in SCOPE_KINDS else [])
        parent = parent.parent
    return scopes


def is_encapsulated(mutation: Mutation, scopes: list[Node]) -> bool:
    lowered = mutation.name.lower()
    if mutation.name.startswith("_") or any(part in lowered for part in ENCAPSULATED_NAME_PARTS):
        return True
    return reads_back(scopes[0], mutation.name) or any(is_owning_writer(scope) for scope in scopes)


def is_test_hook(scope: Node) -> bool:
    arguments = scope.parent
    call = arguments.parent if arguments is not None and arguments.type == "arguments" else None
    return call is not None and node_text(call.child_by_field_name("function")) in TEST_HOOKS


def is_fixture(scope: Node) -> bool:
    holder = scope.parent
    decorators = holder.named_children if holder is not None and holder.type == "decorated_definition" else []
    return any(FIXTURE_MARKER in (node_text(node) or "") for node in decorators if node.type == "decorator")


def is_owning_writer(scope: Node) -> bool:
    lowered = function_name(scope).lower()
    return is_test_hook(scope) or is_fixture(scope) or any(part in lowered for part in OWNING_FUNCTION_PARTS)


def reads_back(scope: Node, name: str) -> bool:
    lookups = {f"{name}.{method}" for method in MEMO_READ_METHODS}
    calls = (node for node in all_nodes(scope) if node.type in CALL_KINDS)
    return any(node_text(node.child_by_field_name("function")) in lookups for node in calls)


def lazily_initialized(root: Node) -> set[str]:
    writes = [node for node in all_nodes(root) if node.type == "augmented_assignment_expression"]
    lazy = [node for node in writes if node_text(node.child_by_field_name("operator")) in LAZY_OPERATORS]
    return {node_text(node.child_by_field_name("left")) or "" for node in lazy}


def is_reportable(mutation: Mutation) -> bool:
    scopes = enclosing_scopes(mutation.node)
    if not scopes or is_encapsulated(mutation, scopes):
        return False
    return not any(binds_locally(scope, mutation.name) for scope in scopes)


def mutation_finding(path: str, mutation: Mutation) -> Finding:
    scope_name = function_name(enclosing_scopes(mutation.node)[0])
    message = f"function '{scope_name}' {mutation.action} module-level '{mutation.name}'; {FIX_HINT}"
    return Finding(path, line_of(mutation.node), RULE_ID, Severity.ERROR, message)


def global_finding(path: str, statement: Node) -> Finding:
    scopes = enclosing_scopes(statement)
    scope_name = f"function '{function_name(scopes[0])}'" if scopes else "module level code"
    names = ", ".join(node_text(name) or "" for name in statement.named_children)
    message = f"{scope_name} rebinds module-level '{names}' through 'global'; {FIX_HINT}"
    return Finding(path, line_of(statement), RULE_ID, Severity.ERROR, message)


def check_global_mutation(parsed: ParsedFile) -> list[Finding]:
    collected = module_globals(parsed.language, parsed.root)
    if collected is None:
        return []
    lazy_names = lazily_initialized(parsed.root)
    globals_kinds = {name: kinds for name, kinds in collected.items() if name not in lazy_names}
    nodes = list(all_nodes(parsed.root))
    found = (find_mutation(node, globals_kinds) for node in nodes) if globals_kinds else iter(())
    mutations = [mutation for mutation in found if mutation is not None and is_reportable(mutation)]
    findings = [mutation_finding(parsed.path, mutation) for mutation in mutations]
    findings += [global_finding(parsed.path, node) for node in nodes if node.type == "global_statement"]
    return sorted(findings, key=lambda finding: finding.line)


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Module-level state written from functions: Python 'global' and in-place writes to module-level "
            "collections; JS/TS reassignment of top-level let/var and writes to top-level array, object, Map, "
            "or Set literals. Private names, cache names, and registration functions are allowed registries."
        ),
        run=check_global_mutation,
    )
)
