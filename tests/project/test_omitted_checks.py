import json

import pytest

from tests.project.conftest import RunProject, rule_findings

PYTHON_PROJECT = {
    "pyproject.toml": (
        '[project]\nname = "app"\nrequires-python = ">=3.13"\n\n'
        '[dependency-groups]\ndev = ["ruff>=0.6", "mypy>=1.0", "flake8>=7.0"]\n'
    ),
    "Makefile": (
        "dev:\n\t./dev\n"
        "check: format-check lint typecheck\n"
        "check-all: check\n"
        "format-check:\n\truff format --check .\n"
        "lint:\n\truff check .\n"
        "typecheck:\n\tmypy .\n"
        "quality:\n\tflake8 .\n"
    ),
}
JAVASCRIPT_PACKAGE = {
    "engines": {"node": ">=22"},
    "devDependencies": {"eslint": "9", "oxlint": "1", "prettier": "3", "typescript": "5"},
    "scripts": {"lint": "eslint .", "strict-lint": "oxlint .", "typecheck": "tsc --noEmit"},
}


@pytest.mark.parametrize(
    ("files", "line", "source"),
    [
        (PYTHON_PROJECT, 11, "Makefile target 'quality'"),
        (
            {
                "package.json": json.dumps(JAVASCRIPT_PACKAGE),
                "Makefile": "dev:\n\tnpm start\ncheck:\n\tnpm run lint\n\tnpm run typecheck\ncheck-all: check\n",
            },
            1,
            "package script 'strict-lint'",
        ),
    ],
)
def test_orphaned_quality_invocation_must_reach_check(
    run_project: RunProject,
    files: dict[str, str],
    line: int,
    source: str,
) -> None:
    _, report = run_project(files)
    assert rule_findings(report, "TL-2") == [
        ("error", f"make check does not run the configured flake8 linter declared in {source}", line)
        if source.startswith("Makefile")
        else ("error", f"make check does not run the configured oxlint linter declared in {source}", line)
    ]


def test_reachable_aliases_and_multiple_tools_are_not_omitted(run_project: RunProject) -> None:
    package = {
        "engines": {"node": ">=22"},
        "devDependencies": {"eslint": "9", "prettier": "3", "typescript": "5"},
        "scripts": {
            "verify": "npm run lint && npm run format",
            "lint": "eslint .",
            "format": "prettier --check .",
            "audit": "npm run lint",
            "typecheck": "tsc --noEmit",
        },
    }
    _, report = run_project(
        {
            "package.json": json.dumps(package),
            "Makefile": "dev:\n\tnpm start\ncheck:\n\tnpm run verify\n\tnpm run typecheck\ncheck-all: check\n",
        }
    )
    assert rule_findings(report, "TL-2") == []


@pytest.mark.parametrize(
    "makefile",
    [
        "dev:\n\tnpm start\ncheck:\n\tnpm run typecheck\ncheck-all: check\n",
        "dev:\n\tnpm start\ncheck:\n\tnpm run typecheck\ncheck-all: check\nlint:\n\tnpm run lint\n",
    ],
)
def test_alias_origins_do_not_own_expanded_tool_calls(run_project: RunProject, makefile: str) -> None:
    package = {
        "engines": {"node": ">=22"},
        "devDependencies": {"eslint": "9", "typescript": "5"},
        "scripts": {"verify": "npm run lint", "lint": "eslint .", "typecheck": "tsc --noEmit"},
    }
    _, report = run_project({"package.json": json.dumps(package), "Makefile": makefile})
    assert rule_findings(report, "TL-2") == [
        ("error", "make check does not run the configured eslint linter declared in package script 'lint'", 1)
    ]


@pytest.mark.parametrize("recipe", ["@echo 'ruff check .'", "./verify-quality"])
def test_mentions_and_dependencies_are_not_configured_checks(
    run_project: RunProject,
    recipe: str,
) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT["pyproject.toml"],
        "Makefile": (
            "dev:\n\t./dev\n"
            "check: format-check lint typecheck\n"
            "check-all: check\n"
            "format-check:\n\truff format --check .\n"
            "lint:\n\truff check .\n"
            "typecheck:\n\tmypy .\n"
            f"quality:\n\t{recipe}\n"
        ),
    }
    _, report = run_project(files)
    assert rule_findings(report, "TL-2") == []
