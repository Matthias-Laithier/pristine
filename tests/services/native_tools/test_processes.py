import os
import signal
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from time import monotonic, sleep

import pytest

from pristine.services.native_tools import processes
from pristine.services.native_tools.processes import ProcessResult, run_process
from tests.services.native_tools.process_fakes import NativeProcess

CHILD_PROGRAM = """
import os, time
reader, writer = os.pipe()
child = os.fork()
if child == 0:
    os.close(reader)
    with open(os.devnull, "wb") as null:
        for descriptor in (0, 1, 2):
            os.dup2(null.fileno(), descriptor)
    os.write(writer, b"ready")
    os.close(writer)
    time.sleep(30)
    os._exit(0)
os.close(writer)
os.read(reader, 5)
os.close(reader)
print(child, flush=True)
os._exit(0)
"""


@pytest.mark.parametrize("output_limit", [4, 5])
def test_combined_output_cap_and_nonreaping_group_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output_limit: int
) -> None:
    child = NativeProcess()
    child.install(monkeypatch)
    result = run_process(["/native/tool", "--version"], tmp_path, output_limit_in_bytes=output_limit)
    if output_limit == 5:
        assert result == ProcessResult(b"abc", b"de", 0, None)
        assert child.events == ["observe-exit", "kill", "reap"]
    else:
        assert result.problem == "native tool exceeded the output limit"
        assert len(result.stdout) + len(result.stderr) <= output_limit
        assert child.events == ["kill", "reap"]
    assert child.stdout.closed and child.stderr.closed


def test_process_deadline_kills_and_reaps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    child = NativeProcess()
    child.install(monkeypatch)
    clock = iter((0.0, 5.0))
    monkeypatch.setattr(processes, "monotonic", lambda: next(clock))
    result = run_process(["/native/tool", "--version"], tmp_path, timeout_in_seconds=5)
    assert result.problem == "native tool timed out"
    assert child.events == ["kill", "reap"]
    assert child.stdout.closed and child.stderr.closed


def test_process_without_nonreaping_status_is_not_started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def must_not_start(command: list[str], **options: object) -> None:
        del command, options
        raise AssertionError("unsupported process control must not spawn")

    monkeypatch.setattr(subprocess, "Popen", must_not_start)
    monkeypatch.delattr(os, "WNOWAIT")
    assert run_process(["/native/tool", "--version"], tmp_path) == ProcessResult(
        b"", b"", None, "native tool processes require non-reaping POSIX child status"
    )


def test_process_start_failure_is_sanitized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(command: list[str], **options: object) -> None:
        del command, options
        raise OSError("sensitive diagnostic")

    monkeypatch.setattr(subprocess, "Popen", unavailable)
    assert run_process(["/native/tool", "--version"], tmp_path) == ProcessResult(
        b"", b"", None, "native tool could not start"
    )


def test_reap_failure_is_explicit_and_closes_pipes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    child = NativeProcess()
    child.reap_failure = True
    child.install(monkeypatch)
    result = run_process(["/native/tool", "--version"], tmp_path)
    assert result.problem == "native tool process could not be reaped"
    assert child.events == ["observe-exit", "kill", "reap"]
    assert child.stdout.closed and child.stderr.closed


def test_one_pipe_close_failure_still_closes_the_other_pipe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    child = NativeProcess()
    child.install(monkeypatch)
    original_close = child.stdout.close

    def failed_close() -> None:
        original_close()
        raise OSError("native output close failed")

    monkeypatch.setattr(child.stdout, "close", failed_close)
    try:
        result = run_process(["/native/tool", "--version"], tmp_path)
        assert result.problem == "native tool process could not be reaped"
        assert child.stdout.closed and child.stderr.closed
    finally:
        child.stderr.close()


@pytest.mark.parametrize("group_remains", [False, True])
def test_zombie_only_permission_error_is_benign_only_after_group_disappears(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, group_remains: bool
) -> None:
    child = NativeProcess()
    child.install(monkeypatch)
    signals: list[int] = []

    def permission_denied(process_group: int, requested_signal: int) -> None:
        assert process_group == child.pid
        signals.append(requested_signal)
        if requested_signal == signal.SIGKILL:
            assert child.returncode is None
            raise PermissionError("fixture zombie group")
        assert child.returncode == 0
        if not group_remains:
            raise ProcessLookupError("fixture group absent")

    monkeypatch.setattr(os, "killpg", permission_denied)
    result = run_process(["/native/tool", "--version"], tmp_path)
    assert result.problem == ("native tool process could not be reaped" if group_remains else None)
    assert signals == [signal.SIGKILL, 0]
    assert child.events == ["observe-exit", "reap"]
    assert child.stdout.closed and child.stderr.closed


@pytest.mark.parametrize("timeout", [float("nan"), 0.0])
def test_process_rejects_nonfinite_or_nonpositive_timeout(tmp_path: Path, timeout: float) -> None:
    with pytest.raises(ValueError, match="bounds"):
        run_process(["/native/tool", "--version"], tmp_path, timeout_in_seconds=timeout)


def test_successful_parent_cannot_leave_a_devnull_child_running(tmp_path: Path) -> None:
    result = run_process([sys.executable, "-c", CHILD_PROGRAM], tmp_path, timeout_in_seconds=5)
    assert result.problem is None
    assert result.returncode == 0
    child_pid = int(result.stdout)
    try:
        assert child_disappeared(child_pid)
    finally:
        with suppress(ProcessLookupError):
            os.kill(child_pid, signal.SIGKILL)


def child_disappeared(child_pid: int) -> bool:
    deadline = monotonic() + 2
    while monotonic() < deadline:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            return True
        sleep(0.01)
    return False
