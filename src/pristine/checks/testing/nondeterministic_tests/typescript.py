lazy from tree_sitter import Node

from pristine.checks.testing.script_scopes import (
    callback,
    framework_call,
    owned_calls,
    parents,
    qualified,
    test_callbacks,
)
from pristine.syntax.calls import callee_of, calls_of
from pristine.syntax.parsing import ParsedFile

FAKE_TIMERS = frozenset(
    {"vi.useFakeTimers", "jest.useFakeTimers", "vitest.vi.useFakeTimers", "@jest/globals.jest.useFakeTimers"}
)
REAL_TIMERS = frozenset(name.replace("useFakeTimers", "useRealTimers") for name in FAKE_TIMERS)
HOOKS = frozenset({"beforeEach", "beforeAll"})
SUITES = frozenset({"describe"})
CALL_KINDS = {"Math.random": "random", "setTimeout": "sleep"}


def suite_of(node: Node) -> Node:
    return next(
        (
            holder
            for holder in parents(node)
            if holder.type == "program" or (holder.type == "call_expression" and framework_call(holder, SUITES))
        ),
        node,
    )


def direct_setup(call: Node, owner: Node) -> bool:
    for holder in parents(call):
        if holder == owner:
            return True
        if holder.type not in {"expression_statement", "statement_block", "await_expression"}:
            return False
    return False


def timer_state(scope: Node, before: int | None = None) -> bool:
    state = False
    for call in owned_calls(scope):
        if before is not None and call.start_byte >= before:
            break
        name = qualified(call)
        if name in REAL_TIMERS:
            state = False
        elif name in FAKE_TIMERS and direct_setup(call, scope):
            state = True
    return state


def hooks_fake(parsed: ParsedFile, test: Node) -> bool:
    owners = {
        suite_of(test),
        *(
            holder
            for holder in parents(test)
            if holder.type == "program" or holder.type == "call_expression" and framework_call(holder, SUITES)
        ),
    }
    hooks = [
        body
        for call, _, _ in calls_of(parsed, "call_expression")
        if framework_call(call, HOOKS)
        and suite_of(call) in owners
        and direct_setup(call, callback(suite_of(call)) or suite_of(call))
        and (body := callback(call)) is not None
    ]
    return (
        bool(hooks)
        and any(timer_state(body) for body in hooks)
        and not any(qualified(call) in REAL_TIMERS for body in hooks for call in owned_calls(body))
    )


def fake_at(call: Node, test: Node, *, setup: bool) -> bool:
    restored = any(qualified(item) in REAL_TIMERS and item.start_byte < call.start_byte for item in owned_calls(test))
    return timer_state(test, call.start_byte) or setup and not restored


def typescript_nondeterministic_calls(parsed: ParsedFile) -> list[tuple[Node, str, str]]:
    found = []
    tests = [(test, hooks_fake(parsed, test)) for test in test_callbacks(parsed)]
    calls = ((test, setup, call) for test, setup in tests for call, _, _ in calls_of(test, "call_expression"))
    for test, setup, call in calls:
        kind = CALL_KINDS.get(qualified(call))
        if kind is None:
            continue
        if kind == "sleep" and fake_at(call, test, setup=setup):
            continue
        found.append((call, callee_of(call), kind))
    return found
