import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from pristine.cli.main import main
from pristine.services.worker_process import WorkerProcess
from tests.report_types import JsonReport, ReportedFinding, ReportedPath, ReportSummary

EXTERNAL_CALL_TIMEOUT_SECONDS = 30


type RunPristine = Callable[..., tuple[int, JsonReport]]


def audit_recording(name: str) -> str:
    return (Path(__file__).parent / "fixtures" / "audit" / f"{name}.json").read_text(encoding="utf-8")


def run_git(directory: Path, *arguments: str) -> None:
    git = shutil.which("git")
    assert git is not None
    subprocess.run([git, "-C", str(directory), *arguments], check=True, timeout=EXTERNAL_CALL_TIMEOUT_SECONDS)


def run_python(program: str, *arguments: str) -> tuple[int, str, str]:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            program,
            *arguments,
        ],
        capture_output=True,
        env={"PYTHONPATH": str(Path(__file__).parents[1] / "src")},
        text=True,
        timeout=EXTERNAL_CALL_TIMEOUT_SECONDS,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def run_cli(*arguments: str) -> tuple[int, str, str]:
    program = (
        "import sys; sys.modules['tree_sitter'] = None; sys.modules['tree_sitter_language_pack'] = None; "
        "from pristine.cli.main import main; raise SystemExit(main())"
    )
    return run_python(program, *arguments)


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
    finding = ReportedFinding(
        path=json_text(entry["path"]),
        line=json_integer(entry["line"]),
        rule_id=json_text(entry["rule_id"]),
        severity=json_text(entry["severity"]),
        message=json_text(entry["message"]),
    )
    kind = entry.get("kind")
    if kind is not None:
        finding["kind"] = json_text(kind)
    return finding


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
        unsupported_files=json_integer(entry.get("unsupported_files", 0)),
        verification_failures=json_integer(entry.get("verification_failures", 0)),
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
        verification_status=json_text(document.get("verification_status", "complete")),
        unsupported=[json_text(entry) for entry in json_list(document.get("unsupported", []))],
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


@pytest.fixture
def worker_process() -> Iterator[WorkerProcess]:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    worker = WorkerProcess(process)
    try:
        yield worker
    finally:
        worker.close()


def rule_findings(report: JsonReport, rule_id: str) -> list[tuple[int, str]]:
    return [(finding["line"], finding["severity"]) for finding in report["findings"] if finding["rule_id"] == rule_id]
