import json

import pytest

from tests.project.conftest import RunProject, rule_findings
from tests.project.quality.test_interpreted import PYPROJECT, PYTHON_MAKEFILE
from tests.project.quality_manifests import ESLINT_CONFIG, PACKAGE

WITHOUT_NATIVE_UNUSED_RULES = '\nselect = ["E4", "E7", "E9"]\n'
MISSING_NATIVE_CHECK = "make check does not enforce dead-code checking; enable Ruff F401 and F841 in the invoked command and configuration, or run another dead-code checker; these are limited native unused-import and unused-local checks"


@pytest.mark.parametrize("recipe", ["echo vulture .", "vulture --help", "vulture --version"])
def test_dead_code_check_must_be_a_real_enforcing_invocation(run_project: RunProject, recipe: str) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace("$(RUN) vulture .", recipe)
    exit_code, report = run_project(
        {
            "pyproject.toml": PYPROJECT + WITHOUT_NATIVE_UNUSED_RULES + '\n[tool.vulture]\npaths = ["."]\n',
            "Makefile": makefile,
        }
    )
    assert exit_code == 1
    assert rule_findings(report, "TL-3") == [
        (
            "error",
            MISSING_NATIVE_CHECK,
            4,
        )
    ]


def test_explicit_pylint_unreachable_check_is_an_alternative(run_project: RunProject) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace(
        "$(RUN) vulture .", "pylint --enable=unreachable ."
    )
    exit_code, report = run_project({"pyproject.toml": PYPROJECT + WITHOUT_NATIVE_UNUSED_RULES, "Makefile": makefile})
    assert (exit_code, report["findings"]) == (0, [])


@pytest.mark.parametrize("configuration", ['paths = ["."]\nexclude = ["*"]', "paths = []"])
def test_vulture_configuration_is_verified_not_just_the_executable(run_project: RunProject, configuration: str) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace("$(RUN) vulture .", "vulture --min-confidence 100")
    exit_code, report = run_project(
        {"pyproject.toml": PYPROJECT + "\n[tool.vulture]\n" + configuration, "Makefile": makefile}
    )
    assert exit_code == (1 if "exclude" in configuration else 3)
    assert len(rule_findings(report, "TL-3")) == 1


@pytest.mark.parametrize(
    "configuration, exit_code",
    [
        ("{}", 0),
        ('{"include": ["dependencies"]}', 1),
        ('{"include": ["files"], "rules": {"files": "warn"}}', 1),
        ("{", 3),
    ],
)
def test_knip_issue_filters_and_configuration_failures(
    run_project: RunProject, configuration: str, exit_code: int
) -> None:
    result, report = run_project(
        {
            "package.json": json.dumps(PACKAGE),
            ".eslintrc.json": ESLINT_CONFIG,
            "Makefile": "dev:\ncheck:\n\tnpm run verify\n\tnpm run typecheck\ncheck-all: check\n",
            "knip.jsonc": configuration,
        }
    )
    assert result == exit_code
    assert len(rule_findings(report, "TL-3")) == (0 if exit_code == 0 else 1)


@pytest.mark.parametrize("command", ["vulture . || true", "-vulture ."])
def test_conditional_dead_code_check_is_not_certified(run_project: RunProject, command: str) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace("$(RUN) vulture .", command)
    exit_code, report = run_project({"pyproject.toml": PYPROJECT, "Makefile": makefile})
    assert exit_code == 3
    assert report["summary"]["verification_failures"] == 1
    assert rule_findings(report, "TL-3") == [
        (
            "warning",
            "cannot verify dead-code checking in make check: conditional, dynamic, piped or failure-suppressing commands require review",
            4,
        )
    ]


@pytest.mark.parametrize(
    "settings, command, exit_code",
    [
        ("true", "tsc --noEmit", 0),
        ("false", "tsc --noEmit", 1),
        ("true", "tsc invoice.ts --noEmit", 1),
        ("false", "tsc --noEmit --noUnusedLocals --noUnusedParameters", 0),
    ],
)
def test_native_typescript_unused_checks_follow_local_inheritance(
    run_project: RunProject, settings: str, command: str, exit_code: int
) -> None:
    package = {
        **PACKAGE,
        "scripts": {"lint": "eslint . && prettier --check .", "typecheck": command, "audit": "npm audit"},
    }
    result, report = run_project(
        {
            "package.json": json.dumps(package),
            ".eslintrc.json": ESLINT_CONFIG,
            "Makefile": "dev:\ncheck:\n\tnpm run lint\n\tnpm run typecheck\ncheck-all: check\n",
            "tsconfig.json": '{"extends": "./config/base.json"}',
            "invoice.ts": "export {};\n",
            "config/base.json": '{"compilerOptions": {"strict": true, "noUnusedLocals": '
            + settings
            + ', "noUnusedParameters": true}}',
        }
    )
    assert result == exit_code
    assert len(rule_findings(report, "TL-3")) == (0 if exit_code == 0 else 1)


def test_pylint_errors_only_does_not_check_unreachable_warnings(run_project: RunProject) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace(
        "$(RUN) vulture .", "pylint --enable=unreachable --errors-only ."
    )
    exit_code, report = run_project({"pyproject.toml": PYPROJECT + WITHOUT_NATIVE_UNUSED_RULES, "Makefile": makefile})
    assert exit_code == 1
    assert rule_findings(report, "TL-3") == [("error", MISSING_NATIVE_CHECK, 4)]
