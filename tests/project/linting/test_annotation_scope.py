from pathlib import Path

import pytest

from tests.project.conftest import RunProject, track_all
from tests.project.linting.lint_cases import ANNOTATIONS, ANNOTATIONS_MAKEFILE, PYTHON_PROJECT, annotation_findings

SOURCE = "def dumps(payload):\n    return payload\n"


@pytest.mark.parametrize(
    "command", ["ruff check typed.py", "ruff check -", "mypy --strict typed.py", "mypy --strict -c pass"]
)
def test_annotation_invocation_must_cover_production_source(run_project: RunProject, command: str) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT + ANNOTATIONS,
        "Makefile": ANNOTATIONS_MAKEFILE.replace("ruff check .", command),
        "typed.py": "def total() -> int:\n    return 1\n",
        "src/legacy.py": SOURCE,
    }
    exit_code, report = run_project(files)
    findings = [finding for finding in report["findings"] if "explicit Python annotations" in finding["message"]]
    assert exit_code != 0
    assert [(finding["severity"], finding.get("kind")) for finding in findings] == [("warning", "verification")]
    assert report["verification_status"] == "incomplete"


@pytest.mark.parametrize("command", ["ruff check .", "ruff check src tests", "mypy --strict src tests"])
def test_annotation_capability_uses_tools_not_a_duplicate_source_analyzer(
    run_project: RunProject, command: str
) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT + ANNOTATIONS,
        "Makefile": ANNOTATIONS_MAKEFILE.replace("ruff check .", command),
        "src/storage.py": SOURCE,
        "tests/test_storage.py": "def test_dumps():\n    assert dumps(1) == 1\n",
    }
    assert annotation_findings(files, run_project) == []


@pytest.mark.parametrize("command", ["ruff check . &", "ruff check --help", "mypy --strict --help"])
def test_nonchecking_annotation_commands_are_not_certified(run_project: RunProject, command: str) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT + ANNOTATIONS,
        "Makefile": ANNOTATIONS_MAKEFILE.replace("ruff check .", command),
        "src/storage.py": SOURCE,
    }
    assert annotation_findings(files, run_project) != []


def test_legacy_ruff_annotation_settings_are_a_verification_gap(run_project: RunProject) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT + '[tool.ruff]\nignore = ["ANN"]\n' + ANNOTATIONS,
        "Makefile": ANNOTATIONS_MAKEFILE,
        "src/storage.py": SOURCE,
    }
    assert annotation_findings(files, run_project) == [("warning", "verification")]


@pytest.mark.parametrize("directive", [".IGNORE:\n", ".ONESHELL:\n", "SHELL := /bin/bash\n"])
def test_make_shell_overrides_are_annotation_verification_gaps(run_project: RunProject, directive: str) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT + ANNOTATIONS,
        "Makefile": directive + ANNOTATIONS_MAKEFILE,
        "src/storage.py": SOURCE,
    }
    assert annotation_findings(files, run_project) == [("warning", "verification")]


@pytest.mark.parametrize("setting", ["exclude = %", "disable_error_code = %(missing)s"])
def test_mypy_ini_percent_values_do_not_crash_verification(run_project: RunProject, setting: str) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT,
        "Makefile": ANNOTATIONS_MAKEFILE.replace("ruff check .", "mypy --strict ."),
        "mypy.ini": "[mypy]\nstrict = True\n" + setting + "\n",
        "src/storage.py": SOURCE,
    }
    _, report = run_project(files)
    assert report["verification_status"] == "incomplete"
    assert [
        (finding["severity"], finding.get("kind"))
        for finding in report["findings"]
        if "explicit Python annotations" in finding["message"]
    ] == [("warning", "verification")]


def test_tracked_gitignored_python_is_not_certified(run_project: RunProject, tmp_path: Path) -> None:
    files = {"src/storage.py": SOURCE, "pyproject.toml": PYTHON_PROJECT + ANNOTATIONS, "Makefile": ANNOTATIONS_MAKEFILE}
    run_project(files)
    track_all(tmp_path)
    assert annotation_findings({".gitignore": "src/storage.py\n"}, run_project) == [("warning", "verification")]
