import pytest

from tests.conftest import RunPristine, rule_findings


def test_function_scoped_var_shadows_globals_after_loop(run_pristine: RunPristine) -> None:
    source = """test("local", () => {
    for (var Math of fakes) {}
    Math.random();
});
"""
    _, report = run_pristine({"tests/random.test.ts": source})
    assert not rule_findings(report, "TST-6")


@pytest.mark.parametrize("extension", ["ts", "tsx", "js"])
def test_destructuring_defaults_are_reads_not_bindings(run_pristine: RunPristine, extension: str) -> None:
    source = """test("random", () => {
    const {value = Math.random()} = options;
    Math.random();
});
"""
    _, report = run_pristine({f"tests/random.test.{extension}": source})
    assert rule_findings(report, "TST-6") == [(2, "warning"), (3, "warning")]
