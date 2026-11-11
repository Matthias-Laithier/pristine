import re

lazy from tree_sitter import Node

from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding, Severity
from pristine.syntax.calls import calls_of
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text
from pristine.syntax.python_calls import import_bindings, qualified_callee
from pristine.syntax.python_tests import is_python_test_module

RULE_ID = "TST-6"
SLEEP = "time.sleep"
RANDOM_MODULE = "random"
UNSEEDED_EXEMPT = frozenset(
    {"random.seed", "random.Random", "random.SystemRandom", "random.getstate", "random.setstate"}
)
SEEDING_CALLS = frozenset({"random.seed", "random.Random"})
IMPLICIT_MODULES = frozenset({"time", "random"})
PATCHED_SLEEP = re.compile(r"[\"'][\w.]*sleep[\"']")
LOOP_KINDS = frozenset({"while_statement", "for_statement"})
ZERO_SLEEP = "(0)"
TEST_PREFIX = "test"
FUNCTION_KIND = "function_definition"
SLEEP_KIND = "sleep"
RANDOM_KIND = "random"
CALL_KINDS = {SLEEP: SLEEP_KIND}
EXEMPTING_TEXT = {SLEEP_KIND: PATCHED_SLEEP}
FIXES = {
    SLEEP_KIND: "wait on an explicit signal from a fake, or poll for the condition with a deadline, instead of guessing a delay",
    RANDOM_KIND: "seed it with random.seed or random.Random(seed), or inject fixed values",
}


def implicit_module_names(source: Node | ParsedFile, heads: set[str]) -> frozenset[str]:
    if not heads:
        return frozenset[str]()
    module_uses = dict.fromkeys(heads, True)
    for node in all_nodes(source):
        if node.type != "identifier":
            continue
        name = node_text(node)
        if name in module_uses:
            module_uses[name] &= node.parent is not None and node.parent.child_by_field_name("object") == node
    return frozenset(head for head, is_module_use in module_uses.items() if is_module_use)


def qualified_name(callee: str, bindings: dict[str, str], implicit_modules: frozenset[str]) -> str:
    head = callee.partition(".")[0]
    return callee if head in implicit_modules else qualified_callee(callee, bindings) or ""


def enclosing_function(node: Node) -> Node | None:
    holder = node.parent
    while holder is not None and holder.type != FUNCTION_KIND:
        holder = holder.parent
    return holder


def is_in_loop(node: Node, function: Node) -> bool:
    holder = node.parent
    while holder is not None and holder != function and holder.type not in LOOP_KINDS:
        holder = holder.parent
    return holder is not None and holder.type in LOOP_KINDS


def is_tolerated_sleep(call: Node, function: Node | None) -> bool:
    if function is None:
        return True
    name = node_text(function.child_by_field_name("name")) or ""
    is_yield = node_text(call.child_by_field_name("arguments")) == ZERO_SLEEP
    return not name.startswith(TEST_PREFIX) or is_in_loop(call, function) or is_yield


def is_tolerated(call: Node, kind: str) -> bool:
    return kind == SLEEP_KIND and is_tolerated_sleep(call, enclosing_function(call))


def has_seed(call: Node) -> bool:
    arguments = call.child_by_field_name("arguments")
    return arguments is not None and arguments.named_child_count > 0


def kind_of(qualified: str, *, seeded: bool) -> str | None:
    is_random = qualified.partition(".")[0] == RANDOM_MODULE and "(" not in qualified
    unseeded = is_random and not seeded and qualified not in UNSEEDED_EXEMPT
    return CALL_KINDS.get(qualified, RANDOM_KIND if unseeded else None)


def exempt_kinds(text: str) -> set[str]:
    return {kind for kind, pattern in EXEMPTING_TEXT.items() if pattern.search(text)}


def nondeterministic_calls(parsed: ParsedFile) -> list[tuple[Node, str, str]]:
    bindings = import_bindings(parsed)
    calls = [(node, callee) for node, callee, _ in calls_of(parsed, "call")]
    heads = {callee.partition(".")[0] for _, callee in calls}
    implicit_modules = implicit_module_names(parsed, (heads & IMPLICIT_MODULES) - bindings.keys())
    calls = [(node, callee, qualified_name(callee, bindings, implicit_modules)) for node, callee in calls]
    seeded = any(qualified in SEEDING_CALLS and has_seed(node) for node, _, qualified in calls)
    exempt = exempt_kinds(parsed.text)
    found = [(node, callee, kind_of(qualified, seeded=seeded)) for node, callee, qualified in calls]
    return [
        (node, callee, kind)
        for node, callee, kind in found
        if kind is not None and kind not in exempt and not is_tolerated(node, kind)
    ]


def check_nondeterministic_tests(parsed: ParsedFile) -> list[Finding]:
    if not is_python_test_module(parsed):
        return []
    return [
        Finding(
            parsed.path,
            line_of(node),
            RULE_ID,
            Severity.WARNING,
            f"test reads the outside world through '{callee}()'; {FIXES[kind]}",
        )
        for node, callee, kind in nondeterministic_calls(parsed)
    ]


CHECK = FileCheck(
    rule_id=RULE_ID,
    title="Nondeterministic Test Patterns",
    summary=(
        "Python test modules (test paths that define test functions or classes, and conftest.py) that sleep "
        "directly in a test function outside loops, or call module-level random functions without a seed. "
        "Files that patch sleep exempt sleeps, a zero sleep is a yield, and a seeded file exempts randomness."
    ),
    run=check_nondeterministic_tests,
)
