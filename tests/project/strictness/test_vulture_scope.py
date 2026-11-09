import pytest

from tests.project.conftest import RunProject, rule_findings
from tests.project.quality.test_interpreted import PYPROJECT, PYTHON_MAKEFILE
from tests.project.strictness.test_dead_code import WITHOUT_NATIVE_UNUSED_RULES

SOURCES = {
    "src/invoices.py": "import math\n\ndef send_invoice():\n    return 1\n    send_receipt()\n",
    "docs/README.md": "Invoices\n",
    "tests/test_invoices.py": "def test_invoice():\n    assert True\n",
}


@pytest.mark.parametrize(
    "selection", ["docs", "docs/README.md", "tests", "src --exclude=*src*", "src --exclude=invoices.py"]
)
def test_vulture_must_select_applicable_python_sources(run_project: RunProject, selection: str) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace(
        "$(RUN) vulture .", f"vulture {selection} --min-confidence 100"
    )
    exit_code, report = run_project(
        {**SOURCES, "pyproject.toml": PYPROJECT + WITHOUT_NATIVE_UNUSED_RULES, "Makefile": makefile}
    )
    assert exit_code == 3
    assert report["summary"]["verification_failures"] == 1
    assert [message for _, message, _ in rule_findings(report, "TL-3")] == [
        "cannot verify vulture dead-code configuration: Vulture does not select discovered Python source src/invoices.py; include applicable source paths or review targeted exclusions"
    ]


@pytest.mark.parametrize("selection", [".", "src", "src tests", "src/invoices.py", "src --exclude=tests"])
def test_vulture_literal_source_scopes_are_verified_without_running_analysis(
    run_project: RunProject, selection: str
) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace(
        "$(RUN) vulture .", f"vulture {selection} --min-confidence 100"
    )
    exit_code, report = run_project(
        {**SOURCES, "pyproject.toml": PYPROJECT + WITHOUT_NATIVE_UNUSED_RULES, "Makefile": makefile}
    )
    assert (exit_code, report["findings"]) == (0, [])


@pytest.mark.parametrize("command", ["cd docs && vulture .", "uv run --directory docs vulture ."])
def test_relocated_vulture_commands_require_source_scope_review(run_project: RunProject, command: str) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace("$(RUN) vulture .", command)
    exit_code, report = run_project({**SOURCES, "pyproject.toml": PYPROJECT, "Makefile": makefile})
    assert exit_code == 3
    assert [message for _, message, _ in rule_findings(report, "TL-3")] == [
        "cannot verify vulture dead-code configuration: Vulture invocation changes working directory; review source and configuration paths relative to that directory"
    ]


@pytest.mark.parametrize("confidence", ["101", "false"])
def test_invalid_vulture_confidence_does_not_certify_analysis(run_project: RunProject, confidence: str) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check")
    exit_code, report = run_project(
        {
            **SOURCES,
            "pyproject.toml": PYPROJECT + "\n[tool.vulture]\nmin_confidence = " + confidence,
            "Makefile": makefile,
        }
    )
    assert exit_code == 3
    assert len(rule_findings(report, "TL-3")) == 1


@pytest.mark.parametrize("selection, exit_code", [("docs", 3), ("src", 0)])
def test_native_ruff_cannot_certify_a_documentation_only_scope(
    run_project: RunProject, selection: str, exit_code: int
) -> None:
    makefile = (
        PYTHON_MAKEFILE.format(format_mode="--check")
        .replace("\t$(RUN) vulture .\n", "")
        .replace("cd app && ", "")
        .replace("ruff check .", f"ruff check {selection}")
    )
    result, report = run_project({**SOURCES, "pyproject.toml": PYPROJECT, "Makefile": makefile})
    assert result == exit_code
    assert len(rule_findings(report, "TL-3")) == (1 if exit_code else 0)


def test_configured_vulture_paths_select_real_sources(run_project: RunProject) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace("$(RUN) vulture .", "vulture --min-confidence 100")
    exit_code, report = run_project(
        {**SOURCES, "pyproject.toml": PYPROJECT + '\n[tool.vulture]\npaths = ["src"]\n', "Makefile": makefile}
    )
    assert (exit_code, report["findings"]) == (0, [])


@pytest.mark.parametrize("setting", ['min_confidence = "invalid"', "unknown_setting = true", "ignore_names = false"])
def test_vulture_rejects_invalid_raw_configuration_before_cli_overrides(run_project: RunProject, setting: str) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace(
        "$(RUN) vulture .", "vulture src --min-confidence 100"
    )
    exit_code, report = run_project(
        {**SOURCES, "pyproject.toml": PYPROJECT + "\n[tool.vulture]\n" + setting, "Makefile": makefile}
    )
    assert exit_code == 3
    assert report["summary"]["verification_failures"] == 1


def test_valid_raw_vulture_setting_can_be_overridden_by_cli(run_project: RunProject) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace(
        "$(RUN) vulture .", "vulture src --min-confidence 100"
    )
    exit_code, report = run_project(
        {**SOURCES, "pyproject.toml": PYPROJECT + "\n[tool.vulture]\nmin_confidence = 101\n", "Makefile": makefile}
    )
    assert (exit_code, report["findings"]) == (0, [])


def test_ruff_inheritance_preserves_root_source_filters(run_project: RunProject) -> None:
    makefile = (
        PYTHON_MAKEFILE.format(format_mode="--check").replace("\t$(RUN) vulture .\n", "").replace("cd app && ", "")
    )
    exit_code, report = run_project(
        {
            **SOURCES,
            "pyproject.toml": PYPROJECT,
            "Makefile": makefile,
            "ruff.toml": 'extend = "base.toml"\nexclude = ["src"]\n',
            "base.toml": '[lint]\nextend-select = ["F", "S", "ASYNC", "DTZ", "G", "T20"]\n',
        }
    )
    assert exit_code == 3
    assert len(rule_findings(report, "TL-3")) == 1


@pytest.mark.parametrize(
    "files",
    [
        {"src/ruff.toml": "[lint]\nselect = []\n"},
        {"src/.ruff.toml": "[lint]\nselect = []\n"},
        {"pyproject.toml": PYPROJECT + 'exclude = ["src"]\n'},
    ],
)
def test_native_ruff_does_not_ignore_closer_configs_or_lint_source_filters(
    run_project: RunProject, files: dict[str, str]
) -> None:
    makefile = (
        PYTHON_MAKEFILE.format(format_mode="--check").replace("\t$(RUN) vulture .\n", "").replace("cd app && ", "")
    )
    exit_code, report = run_project({**SOURCES, "pyproject.toml": PYPROJECT, "Makefile": makefile, **files})
    assert exit_code == 3
    assert report["verification_status"] == "incomplete"
