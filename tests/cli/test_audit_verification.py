import json
from pathlib import Path

import pytest

from pristine.cli.main import main
from pristine.services import osv_scanner
from tests.conftest import json_object, run_cli


def test_audit_help_runs_without_parser_packages_or_scanner() -> None:
    exit_code, stdout, stderr = run_cli("audit", "--help")
    assert exit_code == 0
    assert stderr == ""
    output = " ".join(stdout.split())
    assert "usage: pristine audit [-h] [--json] [--max N] PATH" in output
    assert "Read every rule in full with 'pristine rule all' before coding." in output
    assert "Before finishing, review your change against every rule, including checked rules." in output
    assert "A clean report does not establish full rule compliance." in output
    assert "optional native osv-scanner executable" in output
    assert "No recursive source scan or reachability analysis." in output


@pytest.mark.parametrize(
    "arguments",
    [[], ["first.lock", "second.lock"], [".", "--max", "0"], [".", "--max", "-1"], [".", "--max", "invalid"]],
)
def test_audit_requires_one_path_and_positive_limit(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["audit", *arguments])
    assert exit_info.value.code == 2


@pytest.mark.parametrize("native_case", [("clean", 0, 0), ("vulnerable", 1, 4)])
@pytest.mark.parametrize("extracted_packages", [None, 0, 3])
def test_native_extraction_count_must_match_reported_evidence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    native_case: tuple[str, int, int],
    extracted_packages: int | None,
) -> None:
    sample, exit_code, advisories = native_case
    output = (Path(__file__).parents[2] / "assets" / "audit" / f"{sample}.json").read_text(encoding="utf-8")
    result = osv_scanner.ScannerResult(output, "", exit_code, None, f"/fixtures/{sample}/uv.lock", extracted_packages)
    monkeypatch.setattr(osv_scanner, "scan_lockfile", lambda _: result)
    assert main(["audit", "uv.lock", "--json", "--max", "1"]) == 3
    document = json_object(json.loads(capsys.readouterr().out))
    assert document["verification_status"] == "incomplete"
    assert document["problems"] == ["native extraction count contradicts its package evidence"]
    assert json_object(document["summary"])["advisory_records"] == advisories
