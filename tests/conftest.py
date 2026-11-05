import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from pristine.cli import main

type RunPristine = Callable[..., tuple[int, dict[str, Any]]]


@pytest.fixture
def run_pristine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> RunPristine:
    monkeypatch.chdir(tmp_path)

    def run(files: dict[str, str], *options: str) -> tuple[int, dict[str, Any]]:
        for name, content in files.items():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(content)
        exit_code = main(["check", ".", "--json", *options])
        return exit_code, json.loads(capsys.readouterr().out)

    return run


def rule_findings(report: dict[str, Any], rule_id: str) -> list[tuple[int, str]]:
    return [(finding["line"], finding["severity"]) for finding in report["findings"] if finding["rule_id"] == rule_id]
