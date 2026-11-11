from tests.conftest import RunPristine, rule_findings


def test_function_var_loop_shadows_import_after_loop(run_pristine: RunPristine) -> None:
    source = """import fs from "node:fs";
async function load() {
    for (var fs of fakes) {}
    fs.readFileSync("file");
}
"""
    _, report = run_pristine({"services/files.ts": source})
    assert not rule_findings(report, "SAFE-7")
