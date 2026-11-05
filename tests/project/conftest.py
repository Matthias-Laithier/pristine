from collections.abc import Callable
from pathlib import Path

import pytest

from pristine.cli import main
from tests.conftest import JsonReport, parsed_report, run_git

type RunProject = Callable[[dict[str, str]], tuple[int, JsonReport]]


@pytest.fixture
def run_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> RunProject:
    def run(files: dict[str, str]) -> tuple[int, JsonReport]:
        for name, content in files.items():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(content)
        exit_code = main(["project", str(tmp_path), "--json"])
        return exit_code, parsed_report(capsys.readouterr().out)

    return run


def track_all(directory: Path) -> None:
    for command in (["init", "-q"], ["add", "-A"]):
        run_git(directory, *command)


def rule_findings(report: JsonReport, rule_id: str) -> list[tuple[str, str, int]]:
    return [
        (finding["severity"], finding["message"], finding["line"])
        for finding in report["findings"]
        if finding["rule_id"] == rule_id
    ]
