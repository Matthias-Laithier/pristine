import pytest

from pristine.cli import main
from tests.conftest import RunPristine

LONG_FILE = "".join(f"value_{index} = {index}\n" for index in range(201))


def test_exit_code_is_zero_with_warnings_only(run_pristine: RunPristine) -> None:
    exit_code, report = run_pristine({"values.py": LONG_FILE[: len(LONG_FILE) // 2] + "x = 1\n" * 60})
    assert report["summary"]["warnings"] == 1
    assert exit_code == 0


def test_exit_code_is_one_with_errors(run_pristine: RunPristine) -> None:
    exit_code, _ = run_pristine({"values.py": LONG_FILE})
    assert exit_code == 1


def test_missing_path_is_a_usage_error() -> None:
    assert main(["check", "does/not/exist"]) == 2


def test_text_output_names_rule_and_location(run_pristine: RunPristine, capsys: pytest.CaptureFixture[str]) -> None:
    run_pristine({"values.py": LONG_FILE})
    main(["check", "values.py"])
    assert "values.py:1: CR-1 error: file has 201 lines" in capsys.readouterr().out
