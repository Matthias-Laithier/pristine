lazy from tree_sitter import Node

from pristine.checks.core.values.global_mutation.lazy_initialization import is_lazy_initialization
from pristine.checks.core.values.global_mutation.module_globals import binds_locally, module_globals
from pristine.checks.core.values.global_mutation.ownership import owned_collections
from pristine.checks.core.values.global_mutation.scopes import SCOPE_KINDS
from pristine.checks.core.values.global_mutation.writes import Mutation, find_mutation
from pristine.checks.registry import FileCheck, register_file_check
from pristine.reports.findings import Finding, Severity
from pristine.syntax.parsing import ParsedFile, all_nodes, function_name, line_of, node_text

RULE_ID = "CR-7"
TEST_HOOKS = frozenset({"beforeEach", "beforeAll", "afterEach", "afterAll"})
FIXTURE_MARKER = "fixture"
LAZY_OPERATORS = frozenset({"??=", "||="})
FIX_HINT = "give the state an owner passed to its consumers and keep module-level values as read-only config"


def enclosing_scopes(node: Node) -> list[Node]:
    scopes: list[Node] = []
    parent = node.parent
    while parent is not None:
        scopes.extend([parent] if parent.type in SCOPE_KINDS else [])
        parent = parent.parent
    return scopes


def is_test_hook(scope: Node) -> bool:
    arguments = scope.parent
    call = arguments.parent if arguments is not None and arguments.type == "arguments" else None
    return call is not None and node_text(call.child_by_field_name("function")) in TEST_HOOKS


def is_fixture(scope: Node) -> bool:
    holder = scope.parent
    decorators = holder.named_children if holder is not None and holder.type == "decorated_definition" else []
    return any(FIXTURE_MARKER in (node_text(node) or "") for node in decorators if node.type == "decorator")


def is_test_setup(scope: Node) -> bool:
    return is_test_hook(scope) or is_fixture(scope)


def lazily_initialized(parsed: ParsedFile) -> set[str]:
    writes = [node for node in all_nodes(parsed) if node.type == "augmented_assignment_expression"]
    lazy = [node for node in writes if node_text(node.child_by_field_name("operator")) in LAZY_OPERATORS]
    return {node_text(node.child_by_field_name("left")) or "" for node in lazy}


def writes_module_state(mutation: Mutation) -> bool:
    scopes = enclosing_scopes(mutation.node)
    return bool(scopes) and not any(binds_locally(scope, mutation.name) for scope in scopes)


def is_reportable(mutation: Mutation, owned: set[str]) -> bool:
    scopes = enclosing_scopes(mutation.node)
    if mutation.name in owned or is_lazy_initialization(mutation):
        return False
    return not any(is_test_setup(scope) for scope in scopes)


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
    collected = module_globals(parsed.language, parsed)
    if collected is None:
        return []
    lazy_names = lazily_initialized(parsed)
    globals_kinds = {name: kinds for name, kinds in collected.items() if name not in lazy_names}
    nodes = list(all_nodes(parsed))
    found = (find_mutation(node, globals_kinds) for node in nodes) if globals_kinds else iter(())
    candidates = [mutation for mutation in found if mutation is not None and writes_module_state(mutation)]
    owned = owned_collections(candidates)
    mutations = [mutation for mutation in candidates if is_reportable(mutation, owned)]
    findings = [mutation_finding(parsed.path, mutation) for mutation in mutations]
    findings += [global_finding(parsed.path, node) for node in nodes if node.type == "global_statement"]
    return sorted(findings, key=lambda finding: finding.line)


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Module-level state written from functions: Python 'global' and in-place writes to module-level "
            "collections; JS/TS reassignment of top-level let/var and writes to top-level array, object, Map, "
            "or Set literals. A collection that a function reads before writing it (a memo), stores a parameter "
            "into and hands back (a registration decorator or a subscription), or that test setup resets is allowed."
        ),
        run=check_global_mutation,
    )
)
