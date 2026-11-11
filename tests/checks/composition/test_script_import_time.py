import pytest

from tests.conftest import RunPristine, rule_findings


@pytest.mark.parametrize("suffix", ["ts", "tsx", "js"])
def test_static_class_work_runs_during_import(run_pristine: RunPristine, suffix: str) -> None:
    source = """import fs from "node:fs";
class Settings {
    static region = fs.readFileSync("region");
    region = fs.readFileSync("later");
    static { fs.readFileSync("other"); }
    method(value = fs.readFileSync("default")) { return value; }
    [fs.readFileSync("key")]() {}
}
"""
    _, report = run_pristine({f"settings.{suffix}": source})
    assert rule_findings(report, "CO-13") == [(3, "error"), (5, "error"), (7, "error")]


def test_instance_initializers_and_function_defaults_are_deferred(run_pristine: RunPristine) -> None:
    source = """import fs from "node:fs";
const callback = (value = fs.readFileSync("default")) => value;
class Settings {
    region = fs.readFileSync("region");
    method() { return fs.readFileSync("later"); }
}
"""
    _, report = run_pristine({"settings.ts": source})
    assert not rule_findings(report, "CO-13")
