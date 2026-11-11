lazy from tree_sitter import Node

from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding, Severity
from pristine.syntax.calls import BoundedCall, calls_of
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text
from pristine.syntax.python_calls import has_bound, import_bindings, qualified_callee

RULE_ID = "CR-22"
NOW_FIX = "use datetime.now(UTC)"
TIMESTAMP_FIX = "use datetime.fromtimestamp(timestamp, UTC)"
LOCAL_RESULT_USES = frozenset(
    {"astimezone", "date", "timestamp", "strftime", "year", "month", "day", "weekday", "isoweekday", "hour", "minute"}
)
SCOPE_KINDS = frozenset({"function_definition", "module"})
PASS_THROUGH_KINDS = frozenset({"parenthesized_expression", "binary_operator"})
LOCAL_TIME_CALLS = frozenset({"datetime.datetime.now", "datetime.datetime.today", "datetime.datetime.fromtimestamp"})
NAIVE_CALLS = {
    "datetime.datetime.now": BoundedCall("tz", 0, Severity.ERROR, NOW_FIX),
    "datetime.datetime.today": BoundedCall("tz", None, Severity.ERROR, NOW_FIX),
    "datetime.datetime.utcnow": BoundedCall("tz", None, Severity.ERROR, NOW_FIX),
    "datetime.datetime.fromtimestamp": BoundedCall("tz", 1, Severity.ERROR, TIMESTAMP_FIX),
    "datetime.datetime.utcfromtimestamp": BoundedCall("tz", None, Severity.ERROR, TIMESTAMP_FIX),
}


def attribute_use(value: Node) -> str | None:
    holder = value.parent
    while holder is not None and holder.type in PASS_THROUGH_KINDS:
        holder = holder.parent
    return None if holder is None else node_text(holder.child_by_field_name("attribute"))


def enclosing_scope(node: Node) -> Node:
    scope = node
    while scope.parent is not None and scope.type not in SCOPE_KINDS:
        scope = scope.parent
    return scope


def variable_uses(call: Node) -> list[str | None]:
    assignment = call.parent
    is_assigned = assignment is not None and assignment.type == "assignment"
    target = assignment.child_by_field_name("left") if assignment is not None and is_assigned else None
    if target is None or target.type != "identifier":
        return []
    names = [node for node in all_nodes(enclosing_scope(call)) if node.type == "identifier" and node != target]
    return [attribute_use(name) for name in names if name.text == target.text and not is_member_name(name)]


def is_member_name(name: Node) -> bool:
    return name.parent is not None and name.parent.child_by_field_name("attribute") == name


def is_local_time_use(call: Node, qualified: str) -> bool:
    uses = variable_uses(call) or [attribute_use(call)]
    return qualified in LOCAL_TIME_CALLS and all(use in LOCAL_RESULT_USES for use in uses)


def check_naive_datetimes(parsed: ParsedFile) -> list[Finding]:
    if parsed.language != "python":
        return []
    bindings = import_bindings(parsed)
    findings = []
    for node, callee, arguments in calls_of(parsed, "call"):
        qualified = qualified_callee(callee, bindings) or ""
        call = NAIVE_CALLS.get(qualified)
        if call is not None and not has_bound(arguments, call) and not is_local_time_use(node, qualified):
            message = f"'{callee}()' creates a naive datetime for an instant; {call.fix}"
            findings.append(Finding(parsed.path, line_of(node), RULE_ID, call.severity, message))
    return findings


CHECK = FileCheck(
    rule_id=RULE_ID,
    title="Timezone-Aware Instants",
    summary=(
        "Python naive datetimes for instants: datetime.utcnow, utcfromtimestamp, today, and now or "
        "fromtimestamp without a timezone. date.today is allowed."
    ),
    run=check_naive_datetimes,
)
