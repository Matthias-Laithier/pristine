import json
from collections.abc import Iterator
from io import StringIO
from typing import Literal, override

import pytest

from pristine.engine.worker import main
from pristine.reports.outcomes import Checked

type WorkerEvent = (
    tuple[Literal["read"], str]
    | tuple[Literal["inspect"], str]
    | tuple[Literal["write"], str]
    | tuple[Literal["flush"], str]
)


class RecordingStdout(StringIO):
    def __init__(self, events: list[WorkerEvent]) -> None:
        super().__init__()
        self.events = events

    @override
    def write(self, text: str) -> int:
        self.events.append(("write", text))
        return super().write(text)

    @override
    def flush(self) -> None:
        self.events.append(("flush", self.getvalue()))
        super().flush()


def read_paths(paths: tuple[str, ...], events: list[WorkerEvent]) -> Iterator[str]:
    for path in paths:
        events.append(("read", path))
        yield json.dumps(path) + "\n"


def test_worker_flushes_each_outcome_before_reading_the_next_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[WorkerEvent] = []

    def inspect(path: str) -> Checked:
        events.append(("inspect", path))
        return Checked([])

    stdout = RecordingStdout(events)
    monkeypatch.setattr("sys.stdin", read_paths(("invoice.py", "line\nbreak.py"), events))
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("pristine.engine.worker.inspect_file", inspect)
    main()
    expected_records = [
        {"path": "invoice.py", "kind": "checked", "findings": []},
        {"path": "line\nbreak.py", "kind": "checked", "findings": []},
    ]
    expected_lines = [json.dumps(record) + "\n" for record in expected_records]
    second_flush = "".join(expected_lines)
    assert [json.loads(line) for line in stdout.getvalue().splitlines()] == expected_records
    assert events == [
        ("read", "invoice.py"),
        ("inspect", "invoice.py"),
        ("write", expected_lines[0]),
        ("flush", expected_lines[0]),
        ("read", "line\nbreak.py"),
        ("inspect", "line\nbreak.py"),
        ("write", expected_lines[1]),
        ("flush", second_flush),
    ]


@pytest.mark.parametrize(
    ("input_lines", "expected_error"),
    [
        (["{", json.dumps("invoice.py")], ValueError),
        ([json.dumps(42), json.dumps("invoice.py")], TypeError),
    ],
    ids=["malformed-json", "non-string"],
)
def test_worker_rejects_invalid_protocol_lines(
    input_lines: list[str],
    expected_error: type[Exception],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lines = iter(line + "\n" for line in input_lines)
    written: list[str] = []
    monkeypatch.setattr("sys.stdin", lines)
    monkeypatch.setattr("sys.stdout.write", written.append)

    with pytest.raises(expected_error):
        main()

    assert written == []
