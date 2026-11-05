import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

import pytest

from pristine.cli import main

GIT_TIMEOUT_SECONDS = 30


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


def run_git(directory: Path, *arguments: str) -> None:
    git = shutil.which("git")
    assert git is not None
    subprocess.run([git, "-C", str(directory), *arguments], check=True, timeout=GIT_TIMEOUT_SECONDS)


def json_object(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return dict[str, object](value)


def json_list(value: object) -> list[object]:
    assert isinstance(value, list)
    return list[object](value)


def json_text(value: object) -> str:
    assert isinstance(value, str)
    return value


def json_integer(value: object) -> int:
    assert isinstance(value, int)
    return value


def parsed_finding(value: object) -> ReportedFinding:
    entry = json_object(value)
    return ReportedFinding(
        path=json_text(entry["path"]),
        line=json_integer(entry["line"]),
        rule_id=json_text(entry["rule_id"]),
        severity=json_text(entry["severity"]),
        message=json_text(entry["message"]),
    )


def parsed_path(value: object) -> ReportedPath:
    entry = json_object(value)
    return ReportedPath(path=json_text(entry["path"]), reason=json_text(entry["reason"]))


def parsed_summary(value: object) -> ReportSummary:
    entry = json_object(value)
    return ReportSummary(
        errors=json_integer(entry["errors"]),
        warnings=json_integer(entry["warnings"]),
        checked_files=json_integer(entry["checked_files"]),
        unchecked_files=json_integer(entry["unchecked_files"]),
        skipped_files=json_integer(entry["skipped_files"]),
        missing_paths=json_integer(entry["missing_paths"]),
        by_rule={rule_id: json_integer(count) for rule_id, count in json_object(entry["by_rule"]).items()},
        omitted=json_integer(entry["omitted"]),
    )


def parsed_report(output: str) -> JsonReport:
    document = json_object(json.loads(output))
    return JsonReport(
        summary=parsed_summary(document["summary"]),
        findings=[parsed_finding(entry) for entry in json_list(document["findings"])],
        unchecked=[parsed_path(entry) for entry in json_list(document["unchecked"])],
        skipped=[parsed_path(entry) for entry in json_list(document["skipped"])],
        missing=[json_text(entry) for entry in json_list(document["missing"])],
    )


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
