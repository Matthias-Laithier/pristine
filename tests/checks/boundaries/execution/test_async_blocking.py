from tests.conftest import RunPristine, rule_findings

CHECK_ID = "SAFE-7"
SOURCE = """import asyncio
import time as clock
from subprocess import run
import requests


async def refresh_rates(loop):
    clock.sleep(1)
    run(["git", "status"], timeout=5)
    requests.get(url, timeout=3)
    await asyncio.sleep(1)
    await asyncio.to_thread(run, ["git", "status"])
    await asyncio.to_thread(lambda: requests.get(url, timeout=3))
    await loop.run_in_executor(None, requests.get(url, timeout=3))

    def fetch_in_thread():
        return requests.get(url, timeout=3)

    return [lambda: clock.sleep(1), fetch_in_thread]


def refresh_rates_in_thread():
    clock.sleep(1)
    requests.get(url, timeout=3)
"""


def test_blocking_calls_in_async_functions_are_errors(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"rates.py": SOURCE})
    assert rule_findings(report, CHECK_ID) == [(8, "error"), (9, "error"), (10, "error")]


def test_unimported_names_are_not_resolved(run_pristine: RunPristine) -> None:
    source = "async def refresh_rates(requests):\n    requests.get(url)\n    sleep(1)\n"
    _, report = run_pristine({"rates.py": source})
    assert rule_findings(report, CHECK_ID) == []
