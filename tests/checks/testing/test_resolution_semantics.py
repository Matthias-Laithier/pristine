import pytest

from tests.conftest import RunPristine, rule_findings


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            'import { test as vérifier, expect as égale } from "vitest"; vérifier("é", () => { égale(1).toBe(1); });',
            {"TEST-4": 1},
        ),
        ('test("é", () => { { const Math = { random: () => 0 }; Math.random(); } Math.random(); });', {"TEST-3": 1}),
        ('test("é", () => { { var Math = { random: () => 0 }; } Math.random(); });', {}),
        ('test("é", () => { function inner(Math: { random: () => number }) { Math.random(); } });', {}),
        (
            'describe("outer", () => { beforeEach(() => { vi.useFakeTimers(); }); describe("inner", () => { test("é", () => { setTimeout(() => {}, 1); Math.random(); }); }); });',
            {"TEST-3": 1},
        ),
        (
            'beforeAll(() => { vi.useFakeTimers(); }); test("é", () => { vi.useRealTimers(); setTimeout(() => {}, 1); });',
            {"TEST-3": 1},
        ),
        (
            'beforeEach(() => { vi.useFakeTimers(); vi.useRealTimers(); }); test("é", () => { setTimeout(() => {}, 1); });',
            {"TEST-3": 1},
        ),
        (
            'test("é", () => { const vi = { useFakeTimers: () => 0 }; vi.useFakeTimers(); setTimeout(() => {}, 1); });',
            {"TEST-3": 1},
        ),
    ],
)
def test_resolution_preserves_scope_and_timer_semantics(
    run_pristine: RunPristine, source: str, expected: dict[str, int]
) -> None:
    code, report = run_pristine({"tests/behavior.test.ts": source}, "--jobs", "1")
    assert code in {0, 1}
    assert report["verification_status"] == "complete"
    for check_id in ("TEST-1", "TEST-3", "TEST-4"):
        assert len(rule_findings(report, check_id)) == expected.get(check_id, 0)
