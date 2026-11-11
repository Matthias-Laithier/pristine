import json

import pytest

from tests.project.conftest import RunProject, rule_findings


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        (
            {"pyproject.toml": '[project]\nname = "app"\n'},
            "the Python version is not pinned; set requires-python in pyproject.toml or add one of .python-version",
        ),
        (
            {"package.json": "{}"},
            "the Node.js version is not pinned; set engines.node in package.json or add one of .nvmrc, .node-version",
        ),
    ],
)
def test_unpinned_runtime_is_a_warning(run_project: RunProject, files: dict[str, str], expected: str) -> None:
    _, report = run_project(files)
    assert rule_findings(report, "PROJ-4") == [("warning", expected, 1)]


@pytest.mark.parametrize(
    "files",
    [
        {"pyproject.toml": '[project]\nname = "app"\nrequires-python = ">=3.13"\n'},
        {"pyproject.toml": '[tool.poetry.dependencies]\npython = "^3.12"\n'},
        {"pyproject.toml": '[project]\nname = "app"\n', ".python-version": "3.13\n"},
        {"package.json": json.dumps({"engines": {"node": ">=22"}})},
        {"package.json": json.dumps({"packageManager": "bun@1.3.0"})},
        {"package.json": "{}", ".nvmrc": "22\n"},
        {"package.json": "{}", ".node-version": "22\n"},
    ],
)
def test_pinned_runtime_passes(run_project: RunProject, files: dict[str, str]) -> None:
    _, report = run_project(files)
    assert rule_findings(report, "PROJ-4") == []
