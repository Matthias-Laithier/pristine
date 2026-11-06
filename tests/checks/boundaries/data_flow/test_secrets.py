import json
from pathlib import Path

import pytest

from tests.conftest import RunPristine, rule_findings

FAKE_TOKEN = "ghp" + "_" + "Fake0Token1For2Tests3Only4Abcdefghij"
FAILING_GITLEAKS = "#!/bin/sh\necho 'config is broken' >&2\nexit 3\n"


def test_secret_in_skipped_data_file_is_reported_without_its_value(run_pristine: RunPristine) -> None:
    files = {"settings.json": f'{{\n  "token": "{FAKE_TOKEN}"\n}}\n', "ship.py": "def ship():\n    return 1\n"}
    exit_code, report = run_pristine(files)
    assert exit_code == 1
    assert [finding["path"] for finding in report["findings"] if finding["rule_id"] == "BS-2"] == ["settings.json"]
    assert rule_findings(report, "BS-2") == [(2, "error")]
    assert FAKE_TOKEN not in json.dumps(report)


@pytest.mark.parametrize(("gitleaks_script", "reason"), [(None, "not installed"), (FAILING_GITLEAKS, "code 3")])
def test_scan_that_cannot_run_is_one_warning(
    run_pristine: RunPristine,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    gitleaks_script: str | None,
    reason: str,
) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    if gitleaks_script is not None:
        (tools / "gitleaks").write_text(gitleaks_script)
        (tools / "gitleaks").chmod(0o755)
    monkeypatch.setenv("PATH", str(tools))
    exit_code, report = run_pristine({"ship.py": "def ship():\n    return 1\n"})
    findings = [finding for finding in report["findings"] if finding["rule_id"] == "BS-2"]
    assert exit_code == 3
    assert [(finding["path"], finding["line"], finding["severity"]) for finding in findings] == [(".", 0, "warning")]
    assert findings[0]["kind"] == "verification"
    assert reason in findings[0]["message"]


def test_secret_finding_is_a_code_finding(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"settings.json": f'{{\n  "token": "{FAKE_TOKEN}"\n}}\n'})
    finding = next(finding for finding in report["findings"] if finding["rule_id"] == "BS-2")
    assert "kind" not in finding
