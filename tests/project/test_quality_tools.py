import json

from tests.project.conftest import RunProject, rule_findings

PYPROJECT = '[project]\nname = "app"\n\n[dependency-groups]\ndev = ["ruff>=0.6", "MyPy[reports]==1.0"]\n'
PYTHON_MAKEFILE = (
    "RUN := uv run --project app\n"
    "dev:\n\t./run\n"
    "check: format-check lint\n\t$(RUN) mypy app\n"
    "check-all: check\n"
    "format-check:\n\t@$(RUN) ruff format {format_mode} app\n"
    "lint:\n\tcd app && $(RUN) ruff check .\n"
)
PACKAGE = {
    "devDependencies": {"eslint": "9", "prettier": "3", "typescript": "5"},
    "scripts": {"lint": "eslint . && prettier --check .", "typecheck": "tsc --noEmit", "verify": "npm run lint"},
}
JAVASCRIPT_MAKEFILE = "dev:\n\tnpm start\ncheck:\n\tnpm run verify\n\tpnpm typecheck\ncheck-all: check\n"


def test_python_gate_followed_through_targets_and_variables(run_project: RunProject) -> None:
    exit_code, report = run_project(
        {"pyproject.toml": PYPROJECT, "Makefile": PYTHON_MAKEFILE.format(format_mode="--check")}
    )
    assert (exit_code, report["findings"]) == (0, [])


def test_formatter_must_run_in_check_mode(run_project: RunProject) -> None:
    _, report = run_project({"pyproject.toml": PYPROJECT, "Makefile": PYTHON_MAKEFILE.format(format_mode="")})
    assert rule_findings(report, "TL-3") == [
        (
            "error",
            (
                "make check does not run the formatter in check mode, verifying formatting without rewriting files "
                "(configured: ruff)"
            ),
            4,
        )
    ]


def test_python_project_without_tools(run_project: RunProject) -> None:
    _, report = run_project({"pyproject.toml": '[project]\nname = "app"\n'})
    assert [message.split(";")[0] for _, message, _ in rule_findings(report, "TL-3")] == [
        "no Python formatter configured",
        "no Python linter configured",
        "no Python type checker configured",
    ]


def test_javascript_gate_resolves_package_scripts(run_project: RunProject) -> None:
    files = {"package.json": json.dumps(PACKAGE), "Makefile": JAVASCRIPT_MAKEFILE}
    exit_code, report = run_project(files)
    assert (exit_code, report["findings"]) == (0, [])


def test_typescript_needs_a_type_checker_run(run_project: RunProject) -> None:
    files = {"package.json": json.dumps(PACKAGE), "Makefile": JAVASCRIPT_MAKEFILE.replace("\tpnpm typecheck\n", "")}
    _, report = run_project(files)
    assert [message for _, message, _ in rule_findings(report, "TL-3")] == [
        "make check does not run the type checker (configured: tsc)"
    ]


def test_invalid_manifest_is_listed_as_unchecked(run_project: RunProject) -> None:
    _, report = run_project({"Makefile": JAVASCRIPT_MAKEFILE, "package.json": "{"})
    assert rule_findings(report, "TL-3") == []
    assert [entry["reason"].split(":")[0] for entry in report["unchecked"]] == ["invalid package.json"]
