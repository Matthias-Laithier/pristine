import os
import sys
from collections.abc import Generator, Iterator
from contextlib import contextmanager

from pristine.reports.outcomes import Outcome
from pristine.services.worker_pool import WorkerPool

WORKER_COMMAND = (sys.executable, "-m", "pristine.engine.worker")


def default_jobs() -> int:
    return max(1, (os.cpu_count() or 1) // 2)


def file_size(path: str) -> int:
    try:
        return os.stat(path).st_size
    except OSError:
        return 0


def largest_first(paths: list[str]) -> list[str]:
    return sorted(paths, key=file_size, reverse=True)


def inspect_in_workers(paths: list[str], jobs: int, command: tuple[str, ...] = WORKER_COMMAND) -> dict[str, Outcome]:
    if not paths:
        return {}
    with worker_outcomes(paths, jobs, command) as outcomes:
        return dict(outcomes)


@contextmanager
def worker_outcomes(
    paths: list[str], jobs: int, command: tuple[str, ...] = WORKER_COMMAND
) -> Generator[Iterator[tuple[str, Outcome]]]:
    pool = WorkerPool(largest_first(paths), jobs, command)

    try:
        yield pool.outcomes()
    finally:
        pool.close()
