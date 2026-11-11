import json

import pytest

from tests.project.conftest import RunProject, rule_findings

CONTRACT = "dev:\n\t./run\ncheck:\n\t./test\ncheck-all: check\n"


def install_findings(run_project: RunProject, recipe: str, files: dict[str, str]) -> list[tuple[str, str, int]]:
    _, report = run_project({"Makefile": f"{CONTRACT}install:\n\t{recipe}\n", **files})
    return [finding for finding in rule_findings(report, "PROJ-4") if "lockfile" in finding[1]]


@pytest.mark.parametrize(
    ("recipe", "files", "unfrozen", "frozen"),
    [
        ("uv sync --project app", {}, "uv sync", "uv sync --locked"),
        ("cd web && npm install", {"web/package-lock.json": "{}"}, "npm install", "npm ci"),
        ("pnpm i --prod", {}, "pnpm install", "pnpm install --frozen-lockfile"),
        ("yarn", {}, "yarn install", "yarn install --immutable"),
    ],
)
def test_unfrozen_install_is_an_error(
    run_project: RunProject, recipe: str, files: dict[str, str], unfrozen: str, frozen: str
) -> None:
    message = f"'{unfrozen}' can rewrite the lockfile; install in frozen mode with '{frozen}'"
    assert install_findings(run_project, recipe, files) == [("error", message, 6)]


@pytest.mark.parametrize(
    ("recipe", "files"),
    [
        ("uv sync --locked", {}),
        ("uv sync --frozen --all-extras", {}),
        ("npm install", {}),
        ("npm ci", {"package-lock.json": "{}"}),
        ("npm install -g corepack", {"package-lock.json": "{}"}),
        ("pnpm install --frozen-lockfile", {}),
        ("yarn install --immutable", {}),
        ("yarn add left-pad", {}),
        ("yarn --version", {}),
    ],
)
def test_frozen_or_lockless_install_passes(run_project: RunProject, recipe: str, files: dict[str, str]) -> None:
    assert install_findings(run_project, recipe, files) == []


def test_frozen_environment_variable_in_the_makefile_passes(run_project: RunProject) -> None:
    _, report = run_project({"Makefile": f"export UV_FROZEN := 1\n{CONTRACT}install:\n\tuv sync\n"})
    assert rule_findings(report, "PROJ-4") == []


def test_install_reached_through_a_package_script(run_project: RunProject) -> None:
    package = {"engines": {"node": "22"}, "scripts": {"setup": "pnpm install && pnpm build"}}
    findings = install_findings(run_project, "pnpm run setup", {"package.json": json.dumps(package)})
    assert [(severity, line) for severity, _, line in findings] == [("error", 6)]
