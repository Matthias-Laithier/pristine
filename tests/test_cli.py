import json

import pytest

from pristine.cli import main
from tests.conftest import RunPristine

LONG_FILE = "".join(f"value_{index} = {index}\n" for index in range(201))
COMMENTED_LONG_FILE = LONG_FILE + "# first\n# second\n"


def test_exit_code_is_zero_with_warnings_only(run_pristine: RunPristine) -> None:
    exit_code, report = run_pristine({"values.py": LONG_FILE[: len(LONG_FILE) // 2] + "x = 1\n" * 60})
    assert report["summary"]["warnings"] == 1
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
    assert (
        "\nsummary: 1 error, 0 warnings, 1 checked file, 0 unchecked files, 0 skipped files, 0 missing paths\n"
        in output
    )


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
    assert lines[2] == "... 1 more finding omitted (use --max or --json)"
    assert lines[3].startswith("summary: 3 errors")


def test_max_below_one_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["check", ".", "--max", "0"])
    assert exit_info.value.code == 2
