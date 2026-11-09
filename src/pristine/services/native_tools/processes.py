import os
import selectors
import signal
import subprocess
from contextlib import ExitStack
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from time import monotonic, sleep

__all__ = ["ProcessResult", "run_process"]

PROCESS_TIMEOUT_IN_SECONDS = 300
PROCESS_REAP_TIMEOUT_IN_SECONDS = 5
OUTPUT_LIMIT_IN_BYTES = 8 * 1024 * 1024
READ_CHUNK_IN_BYTES = 65536
PROCESS_STATUS_INTERVAL_IN_SECONDS = 0.01


@dataclass(frozen=True)
class ProcessResult:
    stdout: bytes
    stderr: bytes
    returncode: int | None
    problem: str | None


class _ProcessStopped(Exception):
    pass


def _read_ready(selector: selectors.BaseSelector, remaining_in_seconds: float, capacity_in_bytes: int) -> int:
    if remaining_in_seconds <= 0:
        raise _ProcessStopped("native tool timed out")
    received_in_bytes = 0
    for key, _ in selector.select(timeout=remaining_in_seconds):
        chunk = os.read(key.fd, min(READ_CHUNK_IN_BYTES, capacity_in_bytes - received_in_bytes + 1))
        if not chunk:
            selector.unregister(key.fd)
            continue
        received_in_bytes += len(chunk)
        if received_in_bytes > capacity_in_bytes:
            raise _ProcessStopped("native tool exceeded the output limit")
        buffer = key.data
        if not isinstance(buffer, bytearray):
            raise TypeError("native tool output buffer must be a bytearray")
        buffer.extend(chunk)
    return received_in_bytes


def _capture_output(
    process: subprocess.Popen[bytes], buffers: tuple[bytearray, bytearray], deadline: float, limit_in_bytes: int
) -> None:
    with selectors.DefaultSelector() as selector:
        _register_pipes(selector, process, buffers)
        while selector.get_map():
            limit_in_bytes -= _read_ready(selector, deadline - monotonic(), limit_in_bytes)


def _register_pipes(
    selector: selectors.BaseSelector, process: subprocess.Popen[bytes], buffers: tuple[bytearray, bytearray]
) -> None:
    for stream, buffer in zip((process.stdout, process.stderr), buffers, strict=True):
        if stream is None:
            raise OSError("native tool output pipe is unavailable")
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, buffer)


def _close_process(process: subprocess.Popen[bytes]) -> None:
    with ExitStack() as lifetime:
        for stream in filter(None, (process.stdout, process.stderr)):
            lifetime.callback(stream.close)
        _stop_process(process)


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.returncode is not None:
        return
    denied = False
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        denied = True
    process.wait(timeout=PROCESS_REAP_TIMEOUT_IN_SECONDS)
    if denied:
        _require_group_absent(process.pid)


def _require_group_absent(process_group: int) -> None:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return
    raise PermissionError("native tool process group could not be stopped")


def run_process(
    command: list[str],
    cwd: Path,
    *,
    timeout_in_seconds: float = PROCESS_TIMEOUT_IN_SECONDS,
    output_limit_in_bytes: int = OUTPUT_LIMIT_IN_BYTES,
) -> ProcessResult:
    if not isfinite(timeout_in_seconds) or timeout_in_seconds <= 0 or output_limit_in_bytes < 0:
        raise ValueError("native tool process bounds must be positive")
    if not all(hasattr(os, name) for name in ("waitid", "WNOWAIT", "WEXITED", "WNOHANG", "P_PID")):
        return ProcessResult(b"", b"", None, "native tool processes require non-reaping POSIX child status")
    deadline = monotonic() + timeout_in_seconds
    buffers = (bytearray(), bytearray())
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError, subprocess.SubprocessError:
        return ProcessResult(b"", b"", None, "native tool could not start")
    return _capture_result(process, buffers, deadline, output_limit_in_bytes)


def _capture_result(
    process: subprocess.Popen[bytes], buffers: tuple[bytearray, bytearray], deadline: float, output_limit_in_bytes: int
) -> ProcessResult:
    problem = None
    try:
        _capture_output(process, buffers, deadline, output_limit_in_bytes)
        _wait_for_exit(process, deadline)
    except _ProcessStopped as error:
        problem = str(error)
    except subprocess.TimeoutExpired:
        problem = "native tool timed out"
    except OSError:
        problem = "native tool output could not be read"
    finally:
        problem = _reap_problem(process, problem)
    return ProcessResult(bytes(buffers[0]), bytes(buffers[1]), process.returncode, problem)


def _wait_for_exit(process: subprocess.Popen[bytes], deadline: float) -> None:
    while True:
        remaining_in_seconds = deadline - monotonic()
        if remaining_in_seconds <= 0:
            raise _ProcessStopped("native tool timed out")
        status = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT | os.WNOHANG)
        if status is not None:
            return
        sleep(min(PROCESS_STATUS_INTERVAL_IN_SECONDS, remaining_in_seconds))


def _reap_problem(process: subprocess.Popen[bytes], problem: str | None) -> str | None:
    try:
        _close_process(process)
    except OSError, subprocess.SubprocessError:
        return problem or "native tool process could not be reaped"
    return problem
