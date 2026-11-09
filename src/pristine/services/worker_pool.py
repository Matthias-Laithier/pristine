import selectors
import subprocess
from collections import deque
from collections.abc import Iterator
from contextlib import suppress
from math import ceil
from time import monotonic

from pristine.reports.outcomes import Outcome, Unchecked
from pristine.services.worker_process import (
    LOST_FILE_REASON,
    WorkerOutputError,
    WorkerProcess,
    WorkerSendError,
)

WORKER_STARTUP_SECONDS = 60
SECONDS_PER_FILE = 10
READ_DRAIN_SECONDS = 1
UNLAUNCHABLE_WORKER_REASON = "the worker could not start"


class WorkerPool:
    def __init__(self, paths: list[str], jobs: int, command: tuple[str, ...]) -> None:
        self.pending = deque(paths)
        self.workers: dict[int, WorkerProcess] = {}
        self.selector = selectors.DefaultSelector()
        self.command = command
        self.worker_count = max(1, min(jobs, len(paths)))
        self.launch_error: OSError | None = None

    def outcomes(self) -> Iterator[tuple[str, Outcome]]:
        yield from self.fill()
        while self.pending or self.workers:
            yield from self.retire_expired_workers()
            yield from self.fill()
            self.retire_idle_workers()
            if not self.workers:
                yield from self.drain_unlaunchable_pending()
                return
            yield from self.read_ready_workers()

    def drain_unlaunchable_pending(self) -> Iterator[tuple[str, Outcome]]:
        error = self.launch_error
        reason = UNLAUNCHABLE_WORKER_REASON
        if error is not None:
            reason = f"{UNLAUNCHABLE_WORKER_REASON}: {' '.join(self.command)}: {error}"
        while self.pending:
            yield self.pending.popleft(), Unchecked(reason)

    def fill(self) -> Iterator[tuple[str, Outcome]]:
        while self.pending and len(self.workers) < self.worker_count:
            if not self.add_worker():
                self.worker_count = max(1, len(self.workers))
                break
        for worker in list(self.workers.values()):
            if not self.pending:
                break
            if worker.active_path is not None:
                continue
            path = self.pending.popleft()
            try:
                worker.assign(path, self.assignment_deadline())
            except WorkerSendError as error:
                self.retire_worker(worker)
                yield path, Unchecked(f"{LOST_FILE_REASON}: worker input failed: {error}")

    def add_worker(self) -> bool:
        try:
            process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            self.launch_error = error
            return False
        worker = WorkerProcess(process, monotonic)
        if worker.process.stdin is None or worker.process.stdout is None:
            self.launch_error = OSError("the worker pipes were not opened")
            worker.close()
            return False
        try:
            self.selector.register(worker.process.stdout, selectors.EVENT_READ, worker)
        except OSError as error:
            self.launch_error = error
            worker.close()
            return False
        self.workers[worker.process.stdout.fileno()] = worker
        return True

    def retire_expired_workers(self) -> Iterator[tuple[str, Outcome]]:
        now = monotonic()
        for worker in list(self.workers.values()):
            if worker.active_path is None or now < worker.deadline:
                continue
            yield from self.read_worker(worker, now + READ_DRAIN_SECONDS)
            path = worker.take_active_path()
            if path is None or worker not in self.workers.values():
                continue
            self.retire_worker(worker)
            yield path, Unchecked(LOST_FILE_REASON)

    def read_ready_workers(self) -> Iterator[tuple[str, Outcome]]:
        for key, _ in self.selector.select(timeout=1):
            yield from self.read_worker(key.data, monotonic() + READ_DRAIN_SECONDS)

    def read_worker(self, worker: WorkerProcess, read_deadline: float) -> Iterator[tuple[str, Outcome]]:
        path = worker.active_path
        try:
            outcome = worker.read_outcome(read_deadline)
        except WorkerOutputError as error:
            self.retire_worker(worker)
            if path is not None:
                yield path, Unchecked(error.reason)
            return
        if outcome is not None:
            yield outcome
            return
        if worker.reached_eof:
            reason = worker.exit_failure_reason()
            self.retire_worker(worker)
            if path is not None:
                yield path, Unchecked(reason)

    def retire_idle_workers(self) -> None:
        if self.pending:
            return
        for worker in list(self.workers.values()):
            if worker.active_path is None:
                self.retire_worker(worker)

    def assignment_deadline(self) -> float:
        return monotonic() + WORKER_STARTUP_SECONDS + SECONDS_PER_FILE * ceil(len(self.pending) / self.worker_count)

    def retire_worker(self, worker: WorkerProcess) -> None:
        stdout = worker.process.stdout
        if stdout is not None:
            with suppress(KeyError, OSError, ValueError):
                self.selector.unregister(stdout)
            self.workers.pop(stdout.fileno(), None)
        self.launch_error = None
        worker.close()

    def close(self) -> None:
        while self.workers:
            self.workers.pop(next(iter(self.workers))).close()
        self.selector.close()
