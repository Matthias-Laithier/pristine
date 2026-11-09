import pytest

from tests.project.conftest import RunProject
from tests.project.quality.test_interpreted import PYPROJECT, PYTHON_MAKEFILE
from tests.project.strictness.test_vulture_scope import SOURCES

RULE_GROUPS = '[lint]\nextend-select = ["S", "ASYNC", "DTZ", "G", "T20"]\n'


@pytest.mark.parametrize(
    "configurations",
    [
        {"ruff.toml": RULE_GROUPS, ".ruff.toml": "[lint]\nselect = []\n"},
        {
            "ruff.toml": 'extend = "config/pyproject.toml"\n' + RULE_GROUPS,
            "config/pyproject.toml": "[tool.ruff.lint]\nselect = []\n",
        },
    ],
)
def test_ruff_config_priority_and_pyproject_unwrapping_match_the_tool(
    run_project: RunProject, configurations: dict[str, str]
) -> None:
    makefile = (
        PYTHON_MAKEFILE.format(format_mode="--check").replace("\t$(RUN) vulture .\n", "").replace("cd app && ", "")
    )
    exit_code, report = run_project({**SOURCES, "pyproject.toml": PYPROJECT, "Makefile": makefile, **configurations})
    assert exit_code == 1
    assert report["summary"]["errors"] >= 1


@pytest.mark.parametrize(
    "root, lint, options",
    [
        ("fix = 0\n", "", ""),
        ("fix = 0\n", "", "--no-fix"),
        ("fix-only = []\n", "", "--no-fix-only"),
        ("", "ignore = 0\n", ""),
        ("", "per-file-ignores = []\n", ""),
        ("", 'extend-per-file-ignores = {"*" = [0]}\n', ""),
    ],
)
def test_ruff_raw_consumed_settings_must_match_the_provider_schema(
    run_project: RunProject, root: str, lint: str, options: str
) -> None:
    makefile = (
        PYTHON_MAKEFILE.format(format_mode="--check")
        .replace("\t$(RUN) vulture .\n", "")
        .replace("cd app && ", "")
        .replace("ruff check .", f"ruff check {options} src")
    )
    result, report = run_project(
        {**SOURCES, "pyproject.toml": PYPROJECT, "ruff.toml": root + RULE_GROUPS + lint, "Makefile": makefile}
    )
    assert result == 3
    assert report["verification_status"] == "incomplete"


@pytest.mark.parametrize(
    "inherited, exit_code",
    [
        ("tool = false\n", 3),
        ("tool.ruff = []\n", 3),
        ("tool.ruff = false\n", 3),
        ("tool = {}\n", 0),
        ("tool.ruff = {}\n", 0),
    ],
)
def test_inherited_ruff_pyproject_containers_are_not_coerced_to_defaults(
    run_project: RunProject, inherited: str, exit_code: int
) -> None:
    makefile = (
        PYTHON_MAKEFILE.format(format_mode="--check").replace("\t$(RUN) vulture .\n", "").replace("cd app && ", "")
    )
    result, report = run_project(
        {
            **SOURCES,
            "pyproject.toml": PYPROJECT,
            "ruff.toml": 'extend = "config/pyproject.toml"\n' + RULE_GROUPS,
            "config/pyproject.toml": inherited,
            "Makefile": makefile,
        }
    )
    assert result == exit_code
    assert report["verification_status"] == ("incomplete" if exit_code else "complete")


@pytest.mark.parametrize("legacy", ['select = ["E4", "E7", "E9"]\n', 'ignore = ["F"]\n'])
def test_legacy_ruff_lint_selectors_cannot_invent_default_unused_checks(run_project: RunProject, legacy: str) -> None:
    makefile = (
        PYTHON_MAKEFILE.format(format_mode="--check").replace("\t$(RUN) vulture .\n", "").replace("cd app && ", "")
    )
    result, report = run_project(
        {**SOURCES, "pyproject.toml": PYPROJECT, "ruff.toml": legacy + RULE_GROUPS, "Makefile": makefile}
    )
    assert result == 3
    assert report["verification_status"] == "incomplete"
