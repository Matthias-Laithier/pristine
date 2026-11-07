import json
from pathlib import Path

import pytest

from pristine.cli.main import main


def stream_events(output: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.splitlines()]


def test_stream_prints_path_findings_file_outcomes_and_complete_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "values.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("# notes\n", encoding="utf-8")
    assert main(["check", "values.py", "notes.md", "gone.py", "--jobs", "1", "--stream"]) == 0
    output = capsys.readouterr().out
    assert output.splitlines()[0] == '{"event":"path_findings","phase":"provisional","findings":[]}'
    events = stream_events(output)
    assert len(events) == 4
    assert events[0] == {"event": "path_findings", "phase": "provisional", "findings": []}
    assert events[1] == {
        "event": "file_outcome",
        "phase": "provisional",
        "path": "notes.md",
        "outcome": {"kind": "skipped", "reason": "prose or data file, exempt from these checks"},
    }
    assert events[2] == {
        "event": "file_outcome",
        "phase": "provisional",
        "path": "values.py",
        "outcome": {"kind": "checked", "findings": []},
    }
    assert events[3] == {
        "event": "complete",
        "phase": "complete",
        "verification_status": "complete",
        "summary": {
            "errors": 0,
            "warnings": 0,
            "checked_files": 1,
            "unchecked_files": 0,
            "skipped_files": 1,
            "missing_paths": 1,
            "unsupported_files": 0,
            "verification_failures": 0,
            "by_rule": {},
            "omitted": 0,
        },
        "missing": ["gone.py"],
    }


def test_stream_reports_incomplete_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    assert main(["check", "broken.py", "--jobs", "1", "--stream"]) == 3
    events = stream_events(capsys.readouterr().out)
    assert len(events) == 3
    assert events[0]["event"] == "path_findings"
    assert events[1] == {
        "event": "file_outcome",
        "phase": "provisional",
        "path": "broken.py",
        "outcome": {
            "kind": "unchecked",
            "reason": "could not parse as python: the parser recovered from a syntax error",
        },
    }
    complete = events[2]
    assert complete == {
        "event": "complete",
        "phase": "complete",
        "verification_status": "incomplete",
        "summary": {
            "errors": 0,
            "warnings": 0,
            "checked_files": 0,
            "unchecked_files": 1,
            "skipped_files": 0,
            "missing_paths": 0,
            "unsupported_files": 0,
            "verification_failures": 1,
            "by_rule": {},
            "omitted": 0,
        },
        "missing": [],
    }


@pytest.mark.parametrize("conflict", [("--json",), ("--max", "1")])
def test_stream_rejects_json_and_explicit_max(conflict: tuple[str, ...]) -> None:
    arguments = ["check", ".", "--stream", *conflict]
    with pytest.raises(SystemExit) as exit_info:
        main(arguments)
    assert exit_info.value.code == 2
