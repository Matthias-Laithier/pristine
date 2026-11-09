import json

import pytest

from pristine.cli.main import main
from tests.conftest import RunPristine, json_object

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
def test_text_groups_ranked_files_and_keeps_the_full_fix_checklist(
    run_pristine: RunPristine, capsys: pytest.CaptureFixture[str], options: list[str]
) -> None:
    run_pristine(TRIAGE_FILES)
    assert main(["check", ".", *options]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "fix checklist (all findings; ranked by distinct code rules, then path):"
    assert [line for line in lines if line.startswith("[ ]")] == [
        "[ ] b.py: 2 rules, 2 findings; fix CR-1, CR-3",
        "[ ] c.py: 2 rules, 3 findings; fix CR-12, CR-3",
        "[ ] a.py: 1 rule, 3 findings; fix CR-3",
    ]
    assert lines[2].startswith("b.py:1: CR-1 error:")
    locations = [line.partition(":")[0] for line in lines if line.partition(":")[0] in TRIAGE_FILES]
    assert locations == (["b.py"] if options else ["b.py", "b.py", "c.py", "c.py", "c.py", "a.py", "a.py", "a.py"])
    if options:
        assert "... 7 more findings omitted (CR-12 1, CR-3 6); raise --max or remove --max to see them all" in lines
    assert "by rule: CR-3 6, CR-1 1, CR-12 1" in lines
    assert "verification: complete, 0 failures" in lines


def test_verification_findings_are_not_code_fixes_and_missing_paths_remain_visible(
    run_pristine: RunPristine, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_pristine({"clean.py": "value = 1\n", "broken.py": "def broken(:\n"})
    monkeypatch.setenv("PATH", "")
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
    assert "[ ] .: 0 rules, 1 finding; verify BS-2\n" in output
    assert "missing: gone.py\n" in output
    assert "unchecked: broken.py (" in output
    assert "verification: incomplete, 2 failures\n" in output


def test_clean_report_has_no_triage_work(run_pristine: RunPristine, capsys: pytest.CaptureFixture[str]) -> None:
    run_pristine({"clean.py": "value = 1\n"})
    assert main(["check", ".", "--json"]) == 0
    document = json_object(json.loads(capsys.readouterr().out))
    assert document["triage"] == []
    assert main(["check", "."]) == 0
    assert capsys.readouterr().out.startswith("summary: 0 errors, 0 warnings, 1 checked file")
