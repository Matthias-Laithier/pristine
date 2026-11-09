import pytest

from tests.project.conftest import RunProject, rule_findings
from tests.project.quality.test_interpreted import PYPROJECT, PYTHON_MAKEFILE
from tests.project.quality_manifests import PYTHON_SOURCE


@pytest.mark.parametrize(
    "command, exit_code",
    [
        ("vulture --config tooling.toml . --make-whitelist", 1),
        ("vulture . --exclude=*,tests", 1),
        ("vulture . --exclude=* --exclude=tests", 0),
    ],
)
def test_vulture_configuration_and_exclusion_precedence(run_project: RunProject, command: str, exit_code: int) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace("$(RUN) vulture .", command)
    result, report = run_project(
        {
            **PYTHON_SOURCE,
            "pyproject.toml": PYPROJECT,
            "Makefile": makefile,
            "tooling.toml": '[tool.vulture]\nexclude = ["*"]\n',
        }
    )
    assert result == exit_code
    assert rule_findings(report, "TL-3") == (
        []
        if exit_code == 0
        else [
            (
                "error",
                "vulture does not enforce dead-code checking; remove the all-source exclusion from Vulture's exclude setting or --exclude option",
                1,
            )
        ]
    )
