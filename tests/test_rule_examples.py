import json
from collections.abc import Callable
from pathlib import Path

import pytest

from pristine.checks.registry import file_checks, path_checks
from pristine.cli import main
from tests.conftest import JsonReport, RunPristine, parsed_report, rule_findings
from tests.rule_examples import ExampleKind, RuleExample, rule_examples

type RunProject = Callable[[dict[str, str]], JsonReport]

EXAMPLES = rule_examples()
GOOD_EXAMPLES = [example for example in EXAMPLES if example.kind is ExampleKind.GOOD]
BAD_EXAMPLES = [example for example in EXAMPLES if example.kind is ExampleKind.BAD]
CHECKED_RULES = {check.rule_id for check in [*file_checks(), *path_checks()]}
PROJECT_EXAMPLE_RULES = {"TL-1", "TL-2", "TL-3"}
UNASSERTED_PROJECT_RULES = {
    "TL-4": "its examples are dependency manifests, and TL-4 checks only that a deployable project commits a lockfile",
}
FAILING_SEVERITIES = {"error", "warning"}
PYTHON_PROJECT_CONTEXT = {"pyproject.toml": '[project]\nname = "invoices"\n\n[tool.ruff]\n\n[tool.mypy]\n'}
UNASSERTED_BAD_EXAMPLES = {
    "BS-3-bad": "the HTTP client is an injected collaborator, and BS-3 recognizes only known libraries by their import",
    "CR-8-bad": "a directory tree carries no file contents, and CR-8 judges client-library imports, not file names",
}


@pytest.fixture
def run_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> RunProject:
    def run(files: dict[str, str]) -> JsonReport:
        for name, content in {**PYTHON_PROJECT_CONTEXT, **files}.items():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(content)
        main(["project", str(tmp_path), "--json"])
        return parsed_report(capsys.readouterr().out)

    return run


def failing_findings(report: JsonReport, rule_id: str | None = None) -> list[str]:
    return [
        f"{finding['path']}:{finding['line']} {finding['rule_id']} {finding['message']}"
        for finding in report["findings"]
        if finding["severity"] in FAILING_SEVERITIES and rule_id in (None, finding["rule_id"])
    ]


def example_ids(example: RuleExample) -> str:
    return example.example_id


def checked_bad_examples() -> list[RuleExample]:
    return [
        example
        for example in BAD_EXAMPLES
        if example.rule_id in CHECKED_RULES and example.example_id not in UNASSERTED_BAD_EXAMPLES
    ]


def project_examples(kind: ExampleKind) -> list[RuleExample]:
    return [example for example in EXAMPLES if example.rule_id in PROJECT_EXAMPLE_RULES and example.kind is kind]


@pytest.mark.parametrize("example", GOOD_EXAMPLES, ids=example_ids)
def test_good_example_passes_every_rule(run_pristine: RunPristine, example: RuleExample) -> None:
    _, report = run_pristine(example.files)
    assert not failing_findings(report)


@pytest.mark.parametrize("example", checked_bad_examples(), ids=example_ids)
def test_bad_example_triggers_its_rule(run_pristine: RunPristine, example: RuleExample) -> None:
    _, report = run_pristine(example.files)
    assert rule_findings(report, example.rule_id)


@pytest.mark.parametrize("example", project_examples(ExampleKind.GOOD), ids=example_ids)
def test_good_makefile_example_passes_its_project_rule(run_project: RunProject, example: RuleExample) -> None:
    assert not failing_findings(run_project(example.files), example.rule_id)


@pytest.mark.parametrize("example", project_examples(ExampleKind.BAD), ids=example_ids)
def test_bad_makefile_example_triggers_its_project_rule(run_project: RunProject, example: RuleExample) -> None:
    assert failing_findings(run_project(example.files), example.rule_id)


def test_unasserted_bad_examples_belong_to_checked_rules() -> None:
    checked_bad_examples = {example.example_id for example in BAD_EXAMPLES if example.rule_id in CHECKED_RULES}
    assert set(UNASSERTED_BAD_EXAMPLES) <= checked_bad_examples


def test_every_project_rule_is_asserted_or_listed(capsys: pytest.CaptureFixture[str]) -> None:
    main(["rules", "--json"])
    project_rules = {rule["rule_id"] for rule in json.loads(capsys.readouterr().out) if rule["checked_by"] == "project"}
    assert project_rules == PROJECT_EXAMPLE_RULES | set(UNASSERTED_PROJECT_RULES)
