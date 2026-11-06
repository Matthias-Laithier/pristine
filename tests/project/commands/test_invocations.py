import pytest

from tests.project.conftest import RunProject, rule_findings

PYPROJECT = '[project]\nname = "app"\nrequires-python = ">=3.13"\n\n[dependency-groups]\ndev = ["ruff>=0.6", "MyPy[reports]==1.0"]\n'
MAKEFILE = "RUN := uv run --project app\ndev:\n\t./run\ncheck:\n\t$(RUN) mypy --strict app\ncheck-all: check\n"
ORPHAN = "orphan:\n\t{recipe}\n"


def project_files(recipe: str) -> dict[str, str]:
    return {
        "pyproject.toml": PYPROJECT,
        "package.json": '{"devDependencies":{"typescript":"5"}}',
        "Makefile": f"{MAKEFILE}\n{ORPHAN.format(recipe=recipe)}",
    }


@pytest.mark.parametrize("recipe", ["./run --label flake8", "echo flake8"])
def test_tool_names_in_arguments_are_not_invocations(run_project: RunProject, recipe: str) -> None:
    files = project_files("uv run flake8 .")
    files["Makefile"] = files["Makefile"].replace("$(RUN) mypy --strict app", recipe)
    _, report = run_project(files)
    assert rule_findings(report, "TL-2") == [
        ("error", "make check does not run the configured flake8 linter declared in Makefile target 'orphan'", 8)
    ]


@pytest.mark.parametrize(
    "recipe",
    ["./flake8", "uv run ruff check .", "npx eslint .", "poetry run mypy ."],
)
def test_real_program_invocations_are_reached(run_project: RunProject, recipe: str) -> None:
    files = project_files(recipe)
    files["Makefile"] = files["Makefile"].replace("$(RUN) mypy --strict app", recipe)
    _, report = run_project(files)
    assert rule_findings(report, "TL-2") == []


@pytest.mark.parametrize(
    "recipe",
    [
        "uv run --with ruff mypy .",
        "npx --package typescript tsc --noEmit --pretty false",
        "poetry run -P app mypy .",
    ],
)
def test_option_values_are_not_child_commands(run_project: RunProject, recipe: str) -> None:
    files = project_files("mypy .")
    if "npx" in recipe:
        files.pop("pyproject.toml")
        files["Makefile"] = files["Makefile"].replace("\tmypy .\n", "\ttsc --noEmit --pretty false\n")
    files["Makefile"] = files["Makefile"].replace("$(RUN) mypy --strict app", recipe)
    _, report = run_project(files)
    assert rule_findings(report, "TL-2") == []
