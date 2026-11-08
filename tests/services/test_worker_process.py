import os

from pytest import MonkeyPatch

from pristine.reports.outcomes import Checked
from pristine.services.worker_process import WorkerProcess


def test_a_complete_outcome_wins_at_the_read_deadline(
    worker_process: WorkerProcess,
    monkeypatch: MonkeyPatch,
) -> None:
    worker_process.assign("invoice.py", deadline=100.0)
    outcome_line = b'{"path":"invoice.py","kind":"checked","findings":[]}\n'
    monkeypatch.setattr(os, "read", lambda file_descriptor, size: outcome_line)
    monkeypatch.setattr(worker_process, "clock", lambda: 100.0)

    assert worker_process.read_outcome(read_deadline=100.0) == ("invoice.py", Checked([]))
