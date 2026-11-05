import json
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

import pytest

from pristine.cli import main


class ReportedFinding(TypedDict):
    path: str
    line: int
    rule_id: str
    severity: str
    message: str


class ReportedPath(TypedDict):
    path: str
    reason: str


class ReportSummary(TypedDict):
    errors: int
    warnings: int
    checked_files: int
    unchecked_files: int
    skipped_files: int
    missing_paths: int
    by_rule: dict[str, int]
    omitted: int


class JsonReport(TypedDict):
    summary: ReportSummary
    findings: list[ReportedFinding]
    unchecked: list[ReportedPath]
    skipped: list[ReportedPath]
    missing: list[str]


type RunPristine = Callable[..., tuple[int, JsonReport]]


def parsed_report(output: str) -> JsonReport:
    report: JsonReport = json.loads(output)
    return report


@pytest.fixture
def run_pristine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> RunPristine:
    monkeypatch.chdir(tmp_path)

    def run(files: dict[str, str], *options: str) -> tuple[int, JsonReport]:
        for name, content in files.items():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(content)
        exit_code = main(["check", ".", "--json", *options])
        return exit_code, parsed_report(capsys.readouterr().out)

    return run


def rule_findings(report: JsonReport, rule_id: str) -> list[tuple[int, str]]:
    return [(finding["line"], finding["severity"]) for finding in report["findings"] if finding["rule_id"] == rule_id]
