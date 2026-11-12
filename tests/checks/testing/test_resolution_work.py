from collections import Counter
from collections.abc import Iterator

import pytest

from pristine.checks.registry import file_checks
from pristine.checks.testing import script_scopes
from pristine.checks.testing.nondeterministic_tests import typescript
from pristine.syntax.parsing import parse_file


def test_binding_work_is_reused_per_file(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: Counter[int] = Counter()
    original = script_scopes.scope_bindings

    def counted(scope: script_scopes.Node) -> dict[str, str | None]:
        calls[scope.id] += 1
        return original(scope)

    monkeypatch.setattr(script_scopes, "scope_bindings", counted)
    source = 'import { test, expect } from "vitest"; test("é", () => {' + "expect(1).toBe(1);" * 20 + "});"
    parsed = parse_file("tests/repeated.test.ts", source, "typescript")
    for check in file_checks():
        check.run(parsed)
    assert max(calls.values()) <= 3


def test_hook_discovery_is_once_per_file(monkeypatch: pytest.MonkeyPatch) -> None:
    parsed = parse_file(
        "tests/repeated.test.ts",
        'import { test, beforeEach, vi } from "vitest"; beforeEach(() => { vi.useFakeTimers(); });'
        + "".join(f'test("{index}", () => {{ setTimeout(() => {{}}, 1); }});' for index in range(20)),
        "typescript",
    )
    calls = []
    original = typescript.calls_of

    def counted(
        source: typescript.Node | typescript.ParsedFile, kind: str
    ) -> Iterator[tuple[typescript.Node, str, list[typescript.Node]]]:
        if source is parsed:
            calls.append(source.path)
        return original(source, kind)

    monkeypatch.setattr(typescript, "calls_of", counted)
    assert typescript.typescript_nondeterministic_calls(parsed) == []
    assert len(calls) <= 1


def test_hook_timer_state_is_reused_for_sibling_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    parsed = parse_file(
        "tests/repeated.test.ts",
        "beforeEach(() => { vi.useFakeTimers(); });"
        + "".join(f'test("{index}", () => {{ setTimeout(() => {{}}, 1); }});' for index in range(20)),
        "typescript",
    )
    calls: Counter[int] = Counter()
    original = typescript.timer_state

    def counted(scope: typescript.Node, resolution: script_scopes.ScriptResolution, before: int | None = None) -> bool:
        calls[scope.id] += 1
        return original(scope, resolution, before)

    monkeypatch.setattr(typescript, "timer_state", counted)
    assert typescript.typescript_nondeterministic_calls(parsed) == []
    assert max(calls.values()) == 1
