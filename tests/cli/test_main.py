import json
import tomllib
from pathlib import Path

import pytest

from pristine.cli.main import main
from pristine.cli.rendering import render_text
from pristine.engine import grammar_downloads
from pristine.reports.findings import Finding, Severity
from pristine.reports.report import Report
from tests.conftest import RunPristine

LONG_FILE = "".join(f"value_{index} = {index}\n" for index in range(201))
COMMENTED_LONG_FILE = LONG_FILE + "# first\n# second\n"


def test_exit_code_is_zero_with_warnings_only(run_pristine: RunPristine) -> None:
    source = "def calculate_invoice():\n" + "    value = 1\n" * 30
    exit_code, report = run_pristine({"values.py": source})
    assert report["summary"]["warnings"] == 1
    assert report["summary"]["by_rule"] == {"CR-12": 1}
    assert exit_code == 0


def test_exit_code_is_one_with_errors(run_pristine: RunPristine) -> None:
    exit_code, _ = run_pristine({"values.py": LONG_FILE})
    assert exit_code == 1


def test_missing_paths_are_listed_without_aborting(
    run_pristine: RunPristine, capsys: pytest.CaptureFixture[str]
) -> None:
    run_pristine({"values.py": LONG_FILE})
    assert main(["check", "values.py", "gone.py"]) == 1
    assert "\nmissing: gone.py\n" in capsys.readouterr().out
    assert main(["check", "gone.py", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert (report["missing"], report["summary"]["missing_paths"]) == (["gone.py"], 1)


def test_text_output_names_rule_and_location(run_pristine: RunPristine, capsys: pytest.CaptureFixture[str]) -> None:
    run_pristine({"values.py": LONG_FILE})
    main(["check", "values.py"])
    output = capsys.readouterr().out
    assert "values.py:1: CR-1 error: file has 201 lines" in output
    assert "\nMechanical checks\nsummary: 1 error, 0 warnings\n" in output
    assert "\nfiles: 1 checked file, 0 unchecked files, 0 skipped files, 0 missing paths\n" in output


def test_summary_counts_findings_per_rule_by_count(
    run_pristine: RunPristine, capsys: pytest.CaptureFixture[str]
) -> None:
    _, report = run_pristine({"values.py": COMMENTED_LONG_FILE})
    assert list(report["summary"]["by_rule"].items()) == [("CR-3", 2), ("CR-1", 1)]
    main(["check", "values.py"])
    assert "\nby rule: CR-3 2, CR-1 1\n" in capsys.readouterr().out


def test_max_prints_the_first_findings_and_counts_the_rest(
    run_pristine: RunPristine, capsys: pytest.CaptureFixture[str]
) -> None:
    _, report = run_pristine({"values.py": COMMENTED_LONG_FILE}, "--max", "1")
    assert [finding["rule_id"] for finding in report["findings"]] == ["CR-1"]
    assert (report["summary"]["omitted"], report["summary"]["errors"]) == (2, 3)
    main(["check", "values.py", "--max", "2"])
    lines = capsys.readouterr().out.splitlines()
    assert "... 1 more finding omitted (CR-3 1); raise --max or remove --max to see them all" in lines
    assert any(line.startswith("summary: 3 errors") for line in lines)


def test_max_omission_line_names_the_omitted_rules() -> None:
    report = Report(
        findings=[
            Finding("values.py", 1, "CR-1", Severity.ERROR, "file has 201 lines"),
            Finding("values.py", 202, "CR-3", Severity.ERROR, "comment"),
            Finding("values.py", 203, "CR-3", Severity.ERROR, "another comment"),
        ],
        unchecked={},
        skipped={},
        checked_files=1,
        missing=(),
    )
    assert ("... 2 more findings omitted (CR-3 2); raise --max or remove --max to see them all") in render_text(
        report, 1
    ).splitlines()


@pytest.mark.parametrize("option", ["--max", "--jobs"])
def test_counts_below_one_are_usage_errors(option: str) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["check", ".", option, "0"])
    assert exit_info.value.code == 2


def test_one_job_checks_every_file(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"values.py": LONG_FILE, "other.py": "value = 2\n"}, "--jobs", "1")
    assert (report["summary"]["checked_files"], report["summary"]["errors"]) == (2, 1)


def test_first_use_of_a_grammar_is_announced_once_on_stderr(
    run_pristine: RunPristine, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_pristine({"app.py": "value = 1\n", "other.py": "value = 2\n", "notes.md": "# notes\n"})
    monkeypatch.setattr(grammar_downloads, "cached_languages", frozenset)
    assert main(["check", "."]) == 0
    assert capsys.readouterr().err == "pristine: downloading the python grammar (first use)\n"


def test_version_prints_the_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    pyproject = tomllib.loads((Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8"))
    assert capsys.readouterr().out == f"pristine {pyproject['project']['version']}\n"


@pytest.mark.parametrize("command", [[], ["guide"], ["rule"], ["rules"], ["check"], ["project"]])
def test_help_requires_full_reading_and_review(capsys: pytest.CaptureFixture[str], command: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([*command, "--help"])
    assert exit_info.value.code == 0
    output = " ".join(capsys.readouterr().out.split())
    assert "Read every rule in full with 'pristine rule all' before coding." in output
    assert "Before finishing, review your change against every rule, including checked rules." in output
    assert "Automated checks cover only mechanical parts." in output


@pytest.mark.parametrize("command", ["check", "project"])
def test_clean_reports_still_require_full_rule_review(
    run_pristine: RunPristine, tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    run_pristine({"invoice.py": "invoice_total = 1\n"})
    (tmp_path / "Makefile").write_text("dev:\n\ttrue\ncheck:\n\ttrue\ncheck-all: check\n", encoding="utf-8")
    arguments = [command, "invoice.py" if command == "check" else "."]
    assert main([*arguments, "--json"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["findings"] == []
    assert document["verification_status"] == "complete"
    assert main(arguments) == 0
    output = capsys.readouterr().out
    review = output.partition("\n\nRequired agent review\n")[2]
    sentences = [line.removeprefix("  - ") for line in review.splitlines()]
    assert len(sentences) == 5
    assert "\x1b" not in output
    next_step = "next: " + " ".join(sentences)
    assert document["next_step"] == next_step
    assert "read every rule in full with 'pristine rule all' before coding" in next_step
    assert "review your change against every rule, including checked rules" in next_step
    assert "Automated checks cover only mechanical parts." in next_step
    assert "A clean report does not establish full rule compliance." in next_step
