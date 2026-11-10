import json
from pathlib import Path

import pytest

from tests.project.conftest import RunProject

PYPROJECT = '[project]\nname = "app"\nrequires-python = ">=3.13"\ndependencies = ["{checker}"]\n'
PACKAGE = json.dumps({"engines": {"node": "22"}, "devDependencies": {"typescript": "5"}})
TSCONFIG_WITH_COMMENTS = """{
  // shared settings live in the base
  "extends": ["./config/base.json"], /* trailing commas follow */
  "compilerOptions": {"outDir": "dist",},
}
"""


def strict_findings(files: dict[str, str], run_project: RunProject) -> list[tuple[str, str]]:
    _, report = run_project(files)
    return [
        (finding["severity"], finding["message"])
        for finding in report["findings"]
        if finding["rule_id"] == "TL-3" and "strict mode" in finding["message"]
    ]


def strict_paths(files: dict[str, str], run_project: RunProject, root: Path) -> list[str]:
    _, report = run_project(files)
    findings = [finding for finding in report["findings"] if "strict mode" in finding["message"]]
    return [Path(finding["path"]).relative_to(root.resolve()).as_posix() for finding in findings]


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({"pyproject.toml": PYPROJECT.format(checker="mypy") + "\n[tool.mypy]\nstrict = true\n"}, []),
        ({"setup.cfg": "[mypy]\nstrict = True\n"}, []),
        ({"mypy.ini": "[mypy]\nwarn_return_any = True\n"}, ["mypy.ini"]),
        ({}, ["pyproject.toml"]),
    ],
)
def test_mypy_must_be_strict(
    run_project: RunProject, tmp_path: Path, config: dict[str, str], expected: list[str]
) -> None:
    files = {"pyproject.toml": PYPROJECT.format(checker="mypy"), **config}
    assert strict_paths(files, run_project, tmp_path) == expected


def test_strict_flag_in_the_gate_passes(run_project: RunProject) -> None:
    makefile = "dev:\n\t./run\ncheck:\n\tmypy --strict app\ncheck-all: check\n"
    assert (
        strict_findings({"pyproject.toml": PYPROJECT.format(checker="mypy"), "Makefile": makefile}, run_project) == []
    )


@pytest.mark.parametrize(
    ("checker", "config", "lax"),
    [
        ("pyright", {}, True),
        ("pyright", {"pyrightconfig.json": '{"typeCheckingMode": "strict", // strict\n}'}, False),
        ("basedpyright", {}, False),
        ("basedpyright", {"pyrightconfig.json": '{"typeCheckingMode": "basic"}'}, True),
    ],
)
def test_pyright_modes(run_project: RunProject, checker: str, config: dict[str, str], *, lax: bool) -> None:
    files = {"pyproject.toml": PYPROJECT.format(checker=checker), **config}
    expected = [("error", f'{checker} does not type-check in strict mode; set typeCheckingMode to "strict"')]
    assert strict_findings(files, run_project) == (expected if lax else [])


def test_ty_has_no_strict_mode_to_check(run_project: RunProject) -> None:
    assert strict_findings({"pyproject.toml": PYPROJECT.format(checker="ty")}, run_project) == []


@pytest.mark.parametrize(
    ("base_strict", "expected"),
    [
        ("true", []),
        ("false", [("error", 'TypeScript does not type-check in strict mode; set "strict": true in compilerOptions')]),
    ],
)
def test_typescript_strict_follows_local_extends(
    run_project: RunProject, base_strict: str, expected: list[tuple[str, str]]
) -> None:
    files = {
        "package.json": PACKAGE,
        "tsconfig.json": TSCONFIG_WITH_COMMENTS,
        "config/base.json": f'{{"compilerOptions": {{"strict": {base_strict}, "url": "http://x/*y*/"}}}}',
    }
    assert strict_findings(files, run_project) == expected


def test_solution_config_checks_its_references(run_project: RunProject, tmp_path: Path) -> None:
    files = {
        "package.json": PACKAGE,
        "tsconfig.json": '{"files": [], "references": [{"path": "./tsconfig.app.json"}, {"path": "./node"}]}',
        "tsconfig.app.json": '{"compilerOptions": {"strict": true}}',
        "node/tsconfig.json": '{"compilerOptions": {"strict": false}}',
    }
    assert strict_paths(files, run_project, tmp_path) == ["node/tsconfig.json"]


@pytest.mark.parametrize(
    ("tsconfig", "reason"),
    [
        ('{"extends": "@tsconfig/strictest"}', "tsconfig.json extends @tsconfig/strictest, which is not a local file"),
        ('{"compilerOptions": {', "tsconfig.json is not valid JSON with comments"),
    ],
)
def test_unverifiable_typescript_config_is_a_warning(run_project: RunProject, tsconfig: str, reason: str) -> None:
    [(severity, message)] = strict_findings({"package.json": PACKAGE, "tsconfig.json": tsconfig}, run_project)
    assert severity == "warning"
    assert message.startswith(f"cannot verify that TypeScript type-checks in strict mode: {reason}")


def test_unverifiable_config_is_a_verification_finding(run_project: RunProject) -> None:
    _, report = run_project({"package.json": PACKAGE, "tsconfig.json": '{"extends": "@tsconfig/strictest"}'})
    finding = next(
        finding
        for finding in report["findings"]
        if finding["rule_id"] == "TL-3" and "strict mode" in finding["message"]
    )
    assert finding["kind"] == "verification"
    assert report["verification_status"] == "incomplete"
    assert report["summary"]["verification_failures"] == 1
