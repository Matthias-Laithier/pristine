import re
from collections.abc import Iterator
from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.checks.boundaries.execution.unbounded_fan_out.coroutines import SPAWN_METHODS, is_bounded_work
from pristine.checks.boundaries.execution.unbounded_fan_out.fanned_collections import (
    loop_variables,
    unbounded_collection,
)
from pristine.checks.boundaries.execution.unbounded_fan_out.limiters import Limiters, holds_limiter, limiters_of
from pristine.checks.registry import FileCheck, register_file_check
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
LOOP_KINDS = COMPREHENSION_KINDS | {"for_statement"}
DURABLE_WORKFLOW_PACKAGE = re.compile(r"(temporalio|mistralai\.workflows)(\.|$)")
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


def gathered_loops(source: Node | ParsedFile, bindings: dict[str, str]) -> Iterator[tuple[Node, Node]]:
    for gather, callee, arguments in calls_of(source, "call"):
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


def task_group_loops(source: Node | ParsedFile, bindings: dict[str, str]) -> Iterator[tuple[Node, Node]]:
    for item in (node for node in all_nodes(source) if node.type == "with_item"):
        alias = task_group_alias(item, bindings)
        statement = None if item.parent is None else item.parent.parent
        if alias is not None and statement is not None:
            yield from spawns_in_task_group(statement, alias)


def is_exempt(parsed: ParsedFile, bindings: dict[str, str]) -> bool:
    is_durable_workflow = any(DURABLE_WORKFLOW_PACKAGE.match(module) for module in bindings.values())
    return is_durable_workflow or is_test_path(PurePath(parsed.path))


def fanned_element(call: Node, loop: Node) -> Node | None:
    if loop.type == "call":
        arguments = loop.child_by_field_name("arguments")
        return None if arguments is None or not arguments.named_children else arguments.named_children[0]
    return loop.named_children[0] if call != loop and loop.type != "for_statement" else call


def is_bounded(call: Node, loop: Node, limiters: Limiters) -> bool:
    body = loop.child_by_field_name("body") if loop.type == "for_statement" else None
    element = fanned_element(call, loop)
    is_bounded_loop = body is not None and holds_limiter(body, limiters)
    return is_bounded_loop or (element is not None and is_bounded_work(element, limiters))


def fan_out_finding(parsed: ParsedFile, call: Node, collection: Node) -> Finding:
    message = f"'{callee_of(call)}' fans out over '{node_text(collection)}' with no concurrency bound; {FIX}"
    return Finding(parsed.path, line_of(call), RULE_ID, Severity.WARNING, message)


def check_unbounded_fan_out(parsed: ParsedFile) -> list[Finding]:
    if parsed.language != "python":
        return []
    bindings = import_bindings(parsed)
    if is_exempt(parsed, bindings):
        return []
    limiters = limiters_of(parsed, bindings)
    findings: dict[int, Finding] = {}
    for call, loop in [*gathered_loops(parsed, bindings), *task_group_loops(parsed, bindings)]:
        collection = unbounded_collection(loop)
        if collection is not None and not is_bounded(call, loop, limiters):
            findings.setdefault(line_of(call), fan_out_finding(parsed, call, collection))
    return sorted(findings.values(), key=lambda finding: finding.line)


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Python asyncio.gather over a spread comprehension or map, and TaskGroup spawns in a loop, that start "
            "work per item of an awaited load, where neither the fanned coroutine nor the loop body holds an "
            "asyncio or anyio semaphore or limiter with async with. A load is the awaited result of an imported "
            "function or of a method on another object than the method's own receiver, or a collection derived "
            "from one, and every assignment of the iterated name must be a load. Parameters, functions and methods "
            "of the same file, fields and items of a loaded record, slices, literals, loads that pass a size, "
            "tests, and durable workflow modules are exempt."
        ),
        run=check_unbounded_fan_out,
    )
)
