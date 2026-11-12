lazy from tree_sitter import Node

from pristine.checks.testing.script_scopes import (
    ScriptResolution,
    callback,
    framework_call,
    owned_calls,
    parents,
    script_tests,
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


def suite_of(node: Node, resolution: ScriptResolution) -> Node:
    return next(
        (
            holder
            for holder in parents(node)
            if holder.type == "program"
            or (holder.type == "call_expression" and framework_call(holder, SUITES, resolution))
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


def timer_state(scope: Node, resolution: ScriptResolution, before: int | None = None) -> bool:
    state = False
    for call in owned_calls(scope):
        if before is not None and call.start_byte >= before:
            break
        name = resolution.qualified(call)
        if name in REAL_TIMERS:
            state = False
        elif name in FAKE_TIMERS and direct_setup(call, scope):
            state = True
    return state


class TimerSetup:
    def __init__(self, parsed: ParsedFile, resolution: ScriptResolution) -> None:
        self.resolution = resolution
        self.suites: dict[Node, Node] = {}
        self.hooks = [
            (self.suite(call), body)
            for call, _, _ in calls_of(parsed, "call_expression")
            if framework_call(call, HOOKS, resolution)
            and direct_setup(call, callback(self.suite(call)) or self.suite(call))
            and (body := callback(call)) is not None
        ]
        self.states: dict[Node, tuple[bool, bool]] = {}

    def suite(self, node: Node) -> Node:
        if node not in self.suites:
            self.suites[node] = suite_of(node, self.resolution)
        return self.suites[node]

    def state(self, body: Node) -> tuple[bool, bool]:
        if body not in self.states:
            self.states[body] = (
                timer_state(body, self.resolution),
                any(self.resolution.qualified(call) in REAL_TIMERS for call in owned_calls(body)),
            )
        return self.states[body]


def hooks_fake(test: Node, setup: TimerSetup) -> bool:
    resolution = setup.resolution
    owners = {
        setup.suite(test),
        *(
            holder
            for holder in parents(test)
            if holder.type == "program"
            or holder.type == "call_expression"
            and framework_call(holder, SUITES, resolution)
        ),
    }
    hooks = [body for owner, body in setup.hooks if owner in owners]
    return (
        bool(hooks) and any(setup.state(body)[0] for body in hooks) and not any(setup.state(body)[1] for body in hooks)
    )


def fake_at(call: Node, test: Node, resolution: ScriptResolution, *, setup: bool) -> bool:
    restored = any(
        resolution.qualified(item) in REAL_TIMERS and item.start_byte < call.start_byte for item in owned_calls(test)
    )
    return timer_state(test, resolution, call.start_byte) or setup and not restored


def typescript_nondeterministic_calls(parsed: ParsedFile) -> list[tuple[Node, str, str]]:
    found = []
    tests = script_tests(parsed)
    resolution, callbacks = tests.resolution, tests.callbacks
    if not callbacks:
        return []
    timer_setup = TimerSetup(parsed, resolution)
    tests = [(test, hooks_fake(test, timer_setup)) for test in callbacks]
    calls = ((test, setup, call) for test, setup in tests for call, _, _ in calls_of(test, "call_expression"))
    for test, setup, call in calls:
        kind = CALL_KINDS.get(resolution.qualified(call))
        if kind is None:
            continue
        if kind == "sleep" and fake_at(call, test, resolution, setup=setup):
            continue
        found.append((call, callee_of(call), kind))
    return found
