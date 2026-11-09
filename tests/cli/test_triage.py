import json

import pytest

from pristine.cli.main import main
from pristine.cli.rendering import render_text
from pristine.reports.findings import Finding, FindingKind, Severity
from pristine.reports.report import Report
from tests.conftest import RunPristine, json_object
from tests.services.secret_scan import unavailable_native_tool

LONG_FILE = "".join(f"value_{index} = {index}\n" for index in range(201))
TRIAGE_FILES = {
    "a.py": "# first\n# second\n# third\n",
    "b.py": LONG_FILE + "# first\n",
    "c.py": "def calculate_invoice():\n" + "    value = 1\n" * 30 + "# first\n# second\n",
}
CANONICAL_LOCATIONS = [
    ("a.py", 1),
    ("a.py", 2),
    ("a.py", 3),
    ("b.py", 1),
    ("b.py", 202),
    ("c.py", 1),
    ("c.py", 32),
    ("c.py", 33),
]


@pytest.mark.parametrize("limit", ["1", "8"])
def test_json_triage_uses_all_findings_without_reordering_records(
    run_pristine: RunPristine, capsys: pytest.CaptureFixture[str], limit: str
) -> None:
    run_pristine(TRIAGE_FILES)
    assert main(["check", "c.py", "a.py", "b.py", "--json", "--max", limit]) == 1
    document = json_object(json.loads(capsys.readouterr().out))
    assert document["triage"] == [
        {"path": "b.py", "distinct_rules": 2, "findings": 2, "fix": {"CR-1": 1, "CR-3": 1}, "verify": {}},
        {"path": "c.py", "distinct_rules": 2, "findings": 3, "fix": {"CR-12": 1, "CR-3": 2}, "verify": {}},
        {"path": "a.py", "distinct_rules": 1, "findings": 3, "fix": {"CR-3": 3}, "verify": {}},
    ]
    summary = json_object(document["summary"])
    assert (summary["errors"], summary["warnings"], summary["by_rule"], summary["omitted"]) == (
        7,
        1,
        {"CR-3": 6, "CR-1": 1, "CR-12": 1},
        8 - int(limit),
    )
    findings = document["findings"]
    assert isinstance(findings, list)
    assert [(json_object(entry)["path"], json_object(entry)["line"]) for entry in findings] == (
        CANONICAL_LOCATIONS[: int(limit)]
    )


@pytest.mark.parametrize("options", [[], ["--max", "1"]])
def test_text_groups_ranked_files_and_keeps_full_overviews(
    run_pristine: RunPristine, capsys: pytest.CaptureFixture[str], options: list[str]
) -> None:
    run_pristine(TRIAGE_FILES)
    assert main(["check", ".", *options]) == 1
    output = capsys.readouterr().out
    lines = output.splitlines()
    assert lines[0] == "Findings (ranked by distinct code rules, then path)"
    assert [line for line in lines if line in TRIAGE_FILES] == ["b.py", "c.py", "a.py"]
    assert [line for line in lines if "; fix " in line] == [
        "  2 errors; fix CR-1, CR-3",
        "  2 errors, 1 warning; fix CR-12, CR-3",
        "  3 errors; fix CR-3",
    ]
    assert all(output.count(path) == 1 and f"\n\n{path}\n" in output for path in TRIAGE_FILES)
    finding_lines = output.partition("\nMechanical checks\n")[0].splitlines()
    locations = [line.removeprefix("  - ").partition(":")[0] for line in finding_lines if line.startswith("  - ")]
    assert locations == (
        ["file"] if options else ["file", "line 202", "line 1", "line 32", "line 33", "line 1", "line 2", "line 3"]
    )
    if options:
        assert "... 7 more findings omitted (CR-12 1, CR-3 6); raise --max or remove --max to see them all" in lines
    assert "by rule: CR-3 6, CR-1 1, CR-12 1" in lines
    assert "verification: complete, 0 failures" in lines


def test_verification_findings_are_not_code_fixes_and_missing_paths_remain_visible(
    run_pristine: RunPristine, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_pristine({"clean.py": "value = 1\n", "broken.py": "def broken(:\n"})
    monkeypatch.setattr("pristine.services.gitleaks.resolve_tool", unavailable_native_tool)
    assert main(["check", ".", "gone.py", "--json", "--max", "1"]) == 3
    document = json_object(json.loads(capsys.readouterr().out))
    assert document["triage"] == [
        {"path": ".", "distinct_rules": 0, "findings": 1, "fix": {}, "verify": {"BS-2": 1}},
    ]
    assert document["missing"] == ["gone.py"]
    assert document["verification_status"] == "incomplete"
    unchecked = document["unchecked"]
    assert isinstance(unchecked, list)
    assert [json_object(entry)["path"] for entry in unchecked] == ["broken.py"]
    assert main(["check", ".", "gone.py", "--max", "1"]) == 3
    output = capsys.readouterr().out
    assert "\n.\n  1 warning; verify BS-2\n  - file: verify BS-2 warning:" in output
    assert "missing: gone.py\n" in output
    assert "unchecked: broken.py (" in output
    assert "verification: incomplete, 2 failures\n" in output


@pytest.mark.parametrize("limit", [None, 1])
def test_file_context_keeps_full_paths_and_distinguishes_line_one_from_file_findings(limit: int | None) -> None:
    path = "/workspace/résumés/invoice.py"
    other_path = "/workspace/other/invoice.py"
    report = Report(
        findings=[
            Finding(path, 1, "TL-3", Severity.WARNING, "probe unavailable", FindingKind.VERIFICATION),
            Finding(path, 1, "CR-1", Severity.ERROR, "long file"),
            Finding(path, 1, "CR-3", Severity.ERROR, "first-line comment"),
            Finding(path, 7, "TL-3", Severity.WARNING, "line probe unavailable", FindingKind.VERIFICATION),
            Finding(other_path, 0, "CR-3", Severity.ERROR, "unlocated issue"),
        ],
        unchecked={},
        skipped={},
        checked_files=2,
        missing=(),
    )
    output = render_text(report, limit)
    assert output.count(path) == output.count(other_path) == 1
    assert f"{path}\n  2 errors, 2 warnings; fix CR-1, CR-3; verify TL-3\n" in output
    assert f"{other_path}\n  1 error; fix CR-3\n" in output
    assert "  - file: verify TL-3 warning: probe unavailable\n" in output
    if limit is None:
        assert "  - file: CR-1 error: long file\n  - line 1: CR-3 error: first-line comment\n" in output
        assert "  - line 7: verify TL-3 warning: line probe unavailable\n" in output
        assert "  - file: CR-3 error: unlocated issue\n" in output
    else:
        assert "  - line " not in output
        assert "... 4 more findings omitted (CR-1 1, CR-3 2, TL-3 1);" in output


def test_clean_report_has_no_triage_work(run_pristine: RunPristine, capsys: pytest.CaptureFixture[str]) -> None:
    run_pristine({"clean.py": "value = 1\n"})
    assert main(["check", ".", "--json"]) == 0
    document = json_object(json.loads(capsys.readouterr().out))
    assert document["triage"] == []
    assert main(["check", "."]) == 0
    assert capsys.readouterr().out == (
        "Mechanical checks\n"
        "summary: 0 errors, 0 warnings\n"
        "files: 1 checked file, 0 unchecked files, 0 skipped files, 0 missing paths\n"
        "verification: complete, 0 failures\n\n"
        "Required agent review\n"
        "  - read every rule in full with 'pristine rule all' before coding.\n"
        "  - Before finishing, review your change against every rule, including checked rules.\n"
        "  - Automated checks cover only mechanical parts.\n"
        "  - A clean report does not establish full rule compliance.\n"
        "  - Fix every finding or report it by rule ID as a deliberate break with its reason.\n"
    )
