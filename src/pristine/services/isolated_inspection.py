import os
import subprocess
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

from pristine.outcome_lines import MalformedOutcomeLine, decoded_outcome
from pristine.outcomes import Outcome, Unchecked

WORKER_COMMAND = (sys.executable, "-m", "pristine.worker")
WORKER_STARTUP_SECONDS = 60
SECONDS_PER_FILE = 10
LOST_FILE_REASON = "the parser crashed or timed out on this file"


def reported_outcomes(lines: list[str]) -> Iterator[tuple[str, Outcome]]:
    for line in lines:
        try:
            yield decoded_outcome(line)
        except MalformedOutcomeLine:
            continue


def decoded_results(output: bytes | None) -> dict[str, Outcome]:
    return dict(reported_outcomes((output or b"").decode(errors="replace").splitlines()))


def run_worker(command: tuple[str, ...], paths: list[str]) -> tuple[dict[str, Outcome], bool]:
    request = "\0".join(paths).encode()
    timeout = WORKER_STARTUP_SECONDS + SECONDS_PER_FILE * len(paths)
    try:
        result = subprocess.run(command, input=request, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as expired:
        return decoded_results(expired.stdout), False
    return decoded_results(result.stdout), result.returncode == 0


def inspect_in_one_worker(command: tuple[str, ...], paths: list[str]) -> dict[str, Outcome]:
    outcomes: dict[str, Outcome] = {}
    pending = paths
    while pending:
        reported, finished = run_worker(command, pending)
        outcomes.update(reported)
        pending = [path for path in pending if path not in reported]
        if pending and not finished:
            outcomes[pending[0]] = Unchecked(LOST_FILE_REASON)
            pending = pending[1:]
    return outcomes


def inspect_in_workers(paths: list[str], command: tuple[str, ...] = WORKER_COMMAND) -> dict[str, Outcome]:
    worker_count = max(1, min(os.cpu_count() or 1, len(paths)))
    shares = [paths[index::worker_count] for index in range(worker_count)]
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = executor.map(lambda share: inspect_in_one_worker(command, share), shares)
    return {path: outcome for result in results for path, outcome in result.items()}
