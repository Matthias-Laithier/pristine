import re
from collections.abc import Iterator
from pathlib import PurePath

from tree_sitter import Node

from pristine.checks.registry import FileCheck, register_file_check
from pristine.checks.unbounded_fan_out.fanned_collections import loop_variables, unbounded_collection
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.syntax.calls import callee_of, calls_of
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text
from pristine.syntax.python_calls import import_bindings, qualified_callee
from pristine.syntax.syntax_kinds import COMPREHENSION_KINDS, NESTED_SCOPE_KINDS

RULE_ID = "BS-14"
GATHER = "asyncio.gather"
MAP = "map"
TASK_GROUPS = frozenset({"asyncio.TaskGroup", "anyio.create_task_group"})
SPAWN_METHODS = frozenset({"create_task", "start_soon"})
LOOP_KINDS = COMPREHENSION_KINDS | {"for_statement"}
DURABLE_WORKFLOW_PACKAGE = re.compile(r"(temporalio|mistralai\.workflows)(\.|$)")
CONCURRENCY_BOUND = re.compile(
    r"Semaphore\b|CapacityLimiter|aiometer|\bbatched\(|\bQueue\(|to_thread|run_in_executor"
    r"|(?i:chunk|batch_size|max_length|max_concurren)"
)
FIX = "run it through an asyncio.Semaphore or a bounded pool, or iterate a collection with a named fixed bound"


def starts_new_work(loop: Node) -> bool:
    if loop.type == "call":
        return True
    element = loop.named_children[0] if loop.named_children else None
    receiver = callee_of(element).split(".")[0] if element is not None and element.type == "call" else None
    return receiver is not None and receiver not in loop_variables(loop)


def is_fan_out(spread: Node) -> bool:
    is_mapped = spread.type == "call" and callee_of(spread) == MAP
    return (spread.type in COMPREHENSION_KINDS or is_mapped) and starts_new_work(spread)


def gathered_loops(root: Node, bindings: dict[str, str]) -> Iterator[tuple[Node, Node]]:
    for gather, callee, arguments in calls_of(root, "call"):
        spreads = [argument.named_children[0] for argument in arguments if argument.type == "list_splat"]
        is_gather = qualified_callee(callee, bindings) == GATHER
        yield from ((gather, spread) for spread in spreads if is_gather and is_fan_out(spread))


def task_group_alias(item: Node, bindings: dict[str, str]) -> str | None:
    value = item.child_by_field_name("value")
    if value is None or value.type != "as_pattern":
        return None
    opened = value.named_children[0]
    is_group = qualified_callee(callee_of(opened), bindings) in TASK_GROUPS
    return node_text(value.child_by_field_name("alias")) if is_group else None


def spawning_loop(call: Node, boundary: Node) -> Node | None:
    scope = call.parent
    while scope is not None and scope != boundary and scope.type not in NESTED_SCOPE_KINDS:
        if scope.type in LOOP_KINDS and unbounded_collection(scope) is not None:
            return scope
        scope = scope.parent
    return None


def spawns_in_task_group(statement: Node, alias: str) -> Iterator[tuple[Node, Node]]:
    spawners = {f"{alias}.{method}" for method in SPAWN_METHODS}
    for spawn, callee, _ in calls_of(statement, "call"):
        loop = spawning_loop(spawn, statement) if callee in spawners else None
        if loop is not None:
            yield spawn, loop


def task_group_loops(root: Node, bindings: dict[str, str]) -> Iterator[tuple[Node, Node]]:
    for item in (node for node in all_nodes(root) if node.type == "with_item"):
        alias = task_group_alias(item, bindings)
        statement = None if item.parent is None else item.parent.parent
        if alias is not None and statement is not None:
            yield from spawns_in_task_group(statement, alias)


def is_exempt(parsed: ParsedFile, bindings: dict[str, str]) -> bool:
    is_durable_workflow = any(DURABLE_WORKFLOW_PACKAGE.match(module) for module in bindings.values())
    has_bound = CONCURRENCY_BOUND.search(parsed.text) is not None
    return is_durable_workflow or has_bound or is_test_path(PurePath(parsed.path))


def fan_out_finding(parsed: ParsedFile, call: Node, collection: Node) -> Finding:
    message = f"'{callee_of(call)}' fans out over '{node_text(collection)}' with no concurrency bound; {FIX}"
    return Finding(parsed.path, line_of(call), RULE_ID, Severity.WARNING, message)


def check_unbounded_fan_out(parsed: ParsedFile) -> list[Finding]:
    if parsed.language != "python":
        return []
    bindings = import_bindings(parsed.root)
    if is_exempt(parsed, bindings):
        return []
    findings: dict[int, Finding] = {}
    for call, loop in [*gathered_loops(parsed.root, bindings), *task_group_loops(parsed.root, bindings)]:
        collection = unbounded_collection(loop)
        if collection is not None:
            findings.setdefault(line_of(call), fan_out_finding(parsed, call, collection))
    return sorted(findings.values(), key=lambda finding: finding.line)


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Python asyncio.gather over a spread comprehension or map, and TaskGroup spawns in a loop, that start "
            "work per item of a data collection (ids, records, files, messages, ...) in a file with no semaphore, "
            "limiter, or chunking. Literal, constant, enum, range, page, and batch collections, tests, and durable "
            "workflow modules are exempt."
        ),
        run=check_unbounded_fan_out,
    )
)
