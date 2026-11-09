import pytest

from tests.project.conftest import RunProject, rule_findings
from tests.project.quality.test_interpreted import PYPROJECT, PYTHON_MAKEFILE
from tests.project.quality_manifests import PYTHON_SOURCE
from tests.project.strictness.test_dead_code import MISSING_NATIVE_CHECK


@pytest.mark.parametrize(
    "configuration, command, exit_code",
    [
        (PYPROJECT.replace('"T20"]', '"T20", "F"]'), "ruff check --select E .", 1),
        (PYPROJECT + 'ignore = ["F401"]\n', "ruff check --select F401,F841 .", 0),
        (PYPROJECT + 'select = ["F401", "F841"]\nper-file-ignores = {"*" = ["F"]}\n', "ruff check .", 1),
    ],
)
def test_native_ruff_unused_checks_obey_cli_priority_and_per_file_masks(
    run_project: RunProject, configuration: str, command: str, exit_code: int
) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace("\t$(RUN) vulture .\n", "")
    makefile = makefile.replace("ruff check .", command).replace("cd app && ", "")
    result, report = run_project({**PYTHON_SOURCE, "pyproject.toml": configuration, "Makefile": makefile})
    assert result == exit_code
    assert rule_findings(report, "TL-3") == ([] if exit_code == 0 else [("error", MISSING_NATIVE_CHECK, 4)])


@pytest.mark.parametrize(
    "mode, exit_code",
    [
        ("--show-files", 1),
        ("--show-settings", 1),
        ("--fix-only", 1),
        ("--diff", 1),
        ("--add-noqa", 1),
        ("--add-ignore", 1),
        ("-e", 1),
        ("--watch", 1),
        ("--statistics", 0),
        ("--output-format json", 0),
    ],
)
def test_ruff_native_checks_require_fail_closed_linting(run_project: RunProject, mode: str, exit_code: int) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace("\t$(RUN) vulture .\n", "")
    makefile = makefile.replace("cd app && ", "").replace("ruff check .", f"ruff check {mode} src")
    source = "import math\n\ndef invoice_total():\n    unused = 1\n    return 2\n"
    result, report = run_project({"src/invoices.py": source, "pyproject.toml": PYPROJECT, "Makefile": makefile})
    assert result == exit_code
    assert report["verification_status"] == "complete"
    assert [message for _, message, _ in rule_findings(report, "TL-3")] == (
        []
        if exit_code == 0
        else [
            "make check does not run the linter (configured: ruff)",
            "no Python dead-code checker configured; declare one of pylint, vulture and run it in make check",
        ]
    )


@pytest.mark.parametrize(
    "configuration, options, exit_code",
    [
        ("fix = true\n", "", 3),
        ("fix = true\n", "--no-fix", 0),
        ("fix-only = true\n", "", 3),
        ("fix-only = true\n", "--no-fix-only --no-fix", 0),
        ("", "--per-file-ignores '**/*.py:F401,F841'", 3),
    ],
)
def test_ruff_settings_cannot_silently_suppress_unused_checks(
    run_project: RunProject, configuration: str, options: str, exit_code: int
) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace("\t$(RUN) vulture .\n", "")
    makefile = makefile.replace("cd app && ", "").replace("ruff check .", f"ruff check {options} src")
    settings = configuration + '[lint]\nextend-select = ["S", "ASYNC", "DTZ", "G", "T20"]\n'
    result, report = run_project(
        {**PYTHON_SOURCE, "pyproject.toml": PYPROJECT, "ruff.toml": settings, "Makefile": makefile}
    )
    assert result == exit_code
    assert report["verification_status"] == ("incomplete" if exit_code else "complete")


@pytest.mark.parametrize(
    "setting, exit_code",
    [
        ('per-file-ignores = {"src/invoices.py" = ["F401", "F841"]}\n', 3),
        ('extend-per-file-ignores = {"src/invoices.py" = ["F"]}\n', 3),
        ('per-file-ignores = {"src/invoices.py" = ["T20"]}\n', 0),
        ('per-file-ignores = {"tests/**" = ["F"]}\n', 0),
        ('dummy-variable-rgx = ".*"\n', 3),
        ('pyflakes.allowed-unused-imports = ["math"]\n', 3),
    ],
)
def test_ruff_unused_checks_cannot_certify_application_suppressions(
    run_project: RunProject, setting: str, exit_code: int
) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace("\t$(RUN) vulture .\n", "")
    makefile = makefile.replace("cd app && ", "")
    result, report = run_project({**PYTHON_SOURCE, "pyproject.toml": PYPROJECT + setting, "Makefile": makefile})
    assert result == exit_code
    assert report["verification_status"] == ("incomplete" if exit_code else "complete")
