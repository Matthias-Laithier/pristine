import pytest

from pristine.cli.main import main
from tests.conftest import RunPristine, parsed_report

LONG_FILE = "".join(f"value_{index} = {index}\n" for index in range(201))


def test_parser_recovery_is_incomplete_verification(run_pristine: RunPristine) -> None:
    exit_code, report = run_pristine({"broken.py": "def broken(:\n    return 1\n"})
    assert exit_code == 3
    assert report["verification_status"] == "incomplete"
    assert report["summary"]["verification_failures"] == 1


def test_incomplete_verification_takes_priority_over_rule_errors(run_pristine: RunPristine) -> None:
    exit_code, report = run_pristine(
        {
            "broken.py": "def broken(:\n",
            "notes.md": "# notes\n",
            "values.py": LONG_FILE,
            "source.unknownlang": "value\n",
        }
    )
    assert exit_code == 3
    assert report["summary"]["errors"] == 1
    assert report["summary"]["verification_failures"] == 1
    assert report["unsupported"] == ["source.unknownlang"]
    assert [entry["path"] for entry in report["skipped"]] == ["notes.md"]
    assert report["missing"] == []


def test_parser_unchecked_reports_incomplete_verification_without_other_outcome_failures(
    run_pristine: RunPristine, capsys: pytest.CaptureFixture[str]
) -> None:
    run_pristine({"broken.py": "def broken(:\n", "notes.md": "# notes\n", "source.unknownlang": "value\n"})
    exit_code = main(["check", ".", "gone.py", "--json"])
    report = parsed_report(capsys.readouterr().out)
    assert exit_code == 3
    assert report["verification_status"] == "incomplete"
    assert report["summary"]["verification_failures"] == 1
    assert report["unsupported"] == ["source.unknownlang"]
    assert [entry["path"] for entry in report["skipped"]] == ["notes.md"]
    assert report["missing"] == ["gone.py"]
