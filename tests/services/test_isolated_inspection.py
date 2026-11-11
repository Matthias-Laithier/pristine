import subprocess
import sys
from itertools import chain, repeat
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from pristine.reports.findings import Finding, Severity
from pristine.reports.outcomes import Checked, Outcome, Unchecked
from pristine.services import worker_pool
from pristine.services.isolated_inspection import (
    inspect_in_workers,
    worker_outcomes,
)
from tests.services.worker_commands import (
    BLOCKING_WORKER,
    CHECKING_WORKER,
    CRASHING_WORKER,
    LARGE_FINDING_WORKER,
    LAUNCH_COUNTING_WORKER,
    MISMATCH_WORKER,
    UNLAUNCHABLE_WORKER,
)

LAUNCH_FAILURE_REASON = "the worker could not start: /pristine/worker: launch refused"
LOST_FILE_REASON = "the parser crashed or timed out on this file"
CRASHED_FILE_REASON_PREFIX = "the parser crashed or timed out on this file: worker exit status"
MALFORMED_OUTPUT_REASON = (
    "the worker finished without reporting this file: malformed worker output: the line is not JSON"
)
WRONG_PATH_REASON = "the parser crashed or timed out on this file: the worker reported another path"
WRONG_FINDING_PATH_REASON = "the parser crashed or timed out on this file: a finding reported another path"


def outcomes(paths: list[str], jobs: int, command: tuple[str, ...]) -> dict[str, Outcome]:
    with worker_outcomes(paths, jobs, command) as completed:
        return dict(completed)


def test_idle_workers_take_the_next_file() -> None:
    paths = ["a.py", "b.py", "c.py", "d.py"]
    result = outcomes(paths, jobs=2, command=(sys.executable, "-c", CHECKING_WORKER))
    assert result == {path: Checked([]) for path in paths}


def test_jobs_cap_persistent_processes(tmp_path: Path) -> None:
    launches = tmp_path / "launches.txt"
    command = (sys.executable, "-c", LAUNCH_COUNTING_WORKER, str(launches))
    result = outcomes(["a.py", "b.py", "c.py", "d.py"], jobs=1, command=command)
    assert result == {path: Checked([]) for path in ("a.py", "b.py", "c.py", "d.py")}
    assert launches.read_text().splitlines() == ["worker"]


def test_a_crashing_file_loses_only_itself() -> None:
    result = outcomes(["a.py", "crash.py", "b.py"], jobs=1, command=(sys.executable, "-c", CRASHING_WORKER))
    assert result["a.py"] == Checked([])
    assert result["b.py"] == Checked([])
    crash_outcome = result["crash.py"]
    assert isinstance(crash_outcome, Unchecked)
    assert crash_outcome.reason.startswith(CRASHED_FILE_REASON_PREFIX)


@pytest.mark.parametrize(
    "mismatch",
    ["malformed", "wrong-path", "finding-path"],
    ids=["malformed-line", "wrong-path", "mismatched-finding-path"],
)
def test_a_protocol_mismatch_loses_only_the_active_file(mismatch: str) -> None:
    reasons = {
        "malformed": MALFORMED_OUTPUT_REASON,
        "wrong-path": WRONG_PATH_REASON,
        "finding-path": WRONG_FINDING_PATH_REASON,
    }
    result = outcomes(
        ["a.py", "mismatch.py", "b.py"], jobs=1, command=(sys.executable, "-c", MISMATCH_WORKER, mismatch)
    )
    assert result == {
        "a.py": Checked([]),
        "b.py": Checked([]),
        "mismatch.py": Unchecked(reasons[mismatch]),
    }


def test_a_worker_that_cannot_launch_marks_every_path_unchecked(monkeypatch: MonkeyPatch) -> None:
    def fail_to_launch(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("launch refused")

    monkeypatch.setattr(subprocess, "Popen", fail_to_launch)
    result = outcomes(["a.py", "b.py"], jobs=1, command=UNLAUNCHABLE_WORKER)
    assert result == {"a.py": Unchecked(LAUNCH_FAILURE_REASON), "b.py": Unchecked(LAUNCH_FAILURE_REASON)}


def test_a_special_filename_is_sent_as_one_json_line(tmp_path: Path) -> None:
    path = str(tmp_path / "line\nbreak.py")
    result = outcomes([path], jobs=1, command=(sys.executable, "-c", CHECKING_WORKER))
    assert result == {path: Checked([])}


def test_early_close_cleans_up_processes() -> None:
    with worker_outcomes(["a.py", "b.py"], jobs=1, command=(sys.executable, "-c", CHECKING_WORKER)) as completed:
        assert next(completed) == ("a.py", Checked([]))
    expected = {"a.py": Checked([])}
    command = (sys.executable, "-c", CHECKING_WORKER)
    assert inspect_in_workers(["a.py"], jobs=1, command=command) == expected


def test_one_expired_assignment_cannot_kill_the_remaining_work(monkeypatch: MonkeyPatch) -> None:
    clock = chain((0.0, 30.0), repeat(85.0))
    monkeypatch.setattr(worker_pool, "monotonic", lambda: next(clock))
    command = (sys.executable, "-c", BLOCKING_WORKER)
    result = outcomes(["slow.py", "live.py"], jobs=2, command=command)
    assert result == {
        "slow.py": Unchecked(LOST_FILE_REASON),
        "live.py": Checked([]),
    }


def test_a_valid_outcome_larger_than_sixteen_mib_is_preserved() -> None:
    result = outcomes(["large.py"], jobs=1, command=(sys.executable, "-c", LARGE_FINDING_WORKER))
    expected = Finding("large.py", 1, "STR-4", Severity.WARNING, "x" * 16_777_217)
    assert result == {"large.py": Checked([expected])}
