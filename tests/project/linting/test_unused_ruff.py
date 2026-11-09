import pytest

from tests.project.conftest import RunProject, rule_findings
from tests.project.quality.test_interpreted import PYPROJECT, PYTHON_MAKEFILE
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
    makefile = makefile.replace("ruff check .", command)
    result, report = run_project({"pyproject.toml": configuration, "Makefile": makefile})
    assert result == exit_code
    assert rule_findings(report, "TL-3") == ([] if exit_code == 0 else [("error", MISSING_NATIVE_CHECK, 4)])
