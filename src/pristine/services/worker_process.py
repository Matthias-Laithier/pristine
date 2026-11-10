import json
import os
import subprocess
from collections.abc import Callable
from contextlib import suppress
from time import monotonic

from pristine.reports.outcome_lines import decoded_outcome
from pristine.reports.outcomes import Checked, Outcome

PROCESS_STOP_SECONDS = 5
EXIT_STATUS_WAIT_SECONDS = 1
READ_CHUNK_BYTES = 65536
LOST_FILE_REASON = "the parser crashed or timed out on this file"
UNREPORTED_FILE_REASON = "the worker finished without reporting this file"


class WorkerSendError(Exception):
    pass


class WorkerOutputError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class WorkerProcess:
    def __init__(
        self,
        process: subprocess.Popen[bytes],
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.process = process
        self.active_path: str | None = None
        self.buffer = bytearray()
        self.reached_eof = False
        self.deadline = 0.0
        self.clock = clock
        if process.stdout is not None:
            os.set_blocking(process.stdout.fileno(), False)

    def assign(self, path: str, deadline: float) -> None:
        stdin = self.process.stdin
        if stdin is None:
            raise WorkerSendError("the worker stdin pipe was not opened")
        request = (json.dumps(path) + "\n").encode()
        try:
            stdin.write(request)
            stdin.flush()
        except OSError as error:
            raise WorkerSendError(str(error)) from error
        self.active_path = path
        self.deadline = deadline

    def read_outcome(self, read_deadline: float) -> tuple[str, Outcome] | None:
        while True:
            newline = self.buffer.find(b"\n")
            if newline >= 0:
                return self.outcome_at(newline)
            if self.reached_eof:
                return None
            try:
                chunk = os.read(self.output_fd(), READ_CHUNK_BYTES)
            except BlockingIOError:
                return None
            except OSError as error:
                raise WorkerOutputError(f"{LOST_FILE_REASON}: worker output failed: {error}") from error
            if not chunk:
                self.reached_eof = True
                return None
            self.buffer.extend(chunk)
            newline = self.buffer.find(b"\n")
            if newline >= 0:
                return self.outcome_at(newline)
            if self.clock() >= read_deadline:
                return None

    def take_active_path(self) -> str | None:
        path = self.active_path
        self.active_path = None
        return path

    def outcome_at(self, newline: int) -> tuple[str, Outcome]:
        line = bytes(self.buffer[:newline])
        del self.buffer[: newline + 1]
        if self.active_path is None:
            raise WorkerOutputError(f"{LOST_FILE_REASON}: the worker sent an unassigned outcome")
        try:
            path, outcome = decoded_outcome(line.decode(errors="replace"))
        except ValueError as error:
            raise WorkerOutputError(f"{UNREPORTED_FILE_REASON}: malformed worker output: {error}") from error
        if path != self.active_path:
            raise WorkerOutputError(f"{LOST_FILE_REASON}: the worker reported another path")
        if isinstance(outcome, Checked) and any(finding.path != self.active_path for finding in outcome.findings):
            raise WorkerOutputError(f"{LOST_FILE_REASON}: a finding reported another path")
        active_path = self.active_path
        self.active_path = None
        self.buffer.clear()
        return active_path, outcome

    def output_fd(self) -> int:
        stdout = self.process.stdout
        if stdout is None:
            raise WorkerOutputError(f"{LOST_FILE_REASON}: the worker stdout pipe was not opened")
        return stdout.fileno()

    def exit_failure_reason(self) -> str:
        try:
            return_code = self.process.wait(timeout=EXIT_STATUS_WAIT_SECONDS)
        except subprocess.TimeoutExpired:
            return_code = None
        if return_code == 0:
            return f"{UNREPORTED_FILE_REASON}: worker exit status 0"
        if return_code is None:
            return f"{LOST_FILE_REASON}: the worker closed stdout without exiting"
        return f"{LOST_FILE_REASON}: worker exit status {return_code}"

    def close(self) -> None:
        for stream in (self.process.stdin, self.process.stdout):
            if stream is None:
                continue
            with suppress(OSError):
                stream.close()
        if self.process.poll() is None:
            self.stop()

    def stop(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=PROCESS_STOP_SECONDS)
        except subprocess.TimeoutExpired:
            self.process.kill()
            with suppress(subprocess.TimeoutExpired):
                self.process.wait(timeout=PROCESS_STOP_SECONDS)
