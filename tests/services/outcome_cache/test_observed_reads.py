import os
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from pristine.checks.definitions import FileCheck
from pristine.cli import main as cli
from pristine.engine import inspection
from pristine.reports.findings import Finding, Severity
from pristine.reports.outcomes import Outcome
from pristine.syntax.parsing import ParsedFile
from tests.services.outcome_cache.conftest import Scan, write

NEIGHBOR = "neighbor.cfg"


def opened_flag(location: Path) -> bool:
    try:
        return location.read_text().strip() == "flag"
    except FileNotFoundError:
        return False


def reading_check(read: str) -> FileCheck:
    def run(parsed: ParsedFile) -> list[Finding]:
        location = Path(parsed.path).parent / NEIGHBOR
        found = {
            "open": lambda: opened_flag(location),
            "exists": location.exists,
            "listing": lambda: NEIGHBOR in os.listdir(location.parent),
        }[read]()
        return [Finding(parsed.path, 1, "TEST-9", Severity.WARNING, "neighbor flag")] if found else []

    return FileCheck("TEST-9", "Neighbor", "Reads a neighbor file.", run)


@contextmanager
def in_process(paths: list[str], jobs: int) -> Generator[Iterator[tuple[str, Outcome]]]:
    del jobs
    yield ((path, inspection.inspect_file(path)) for path in paths)


@pytest.mark.parametrize("read", ["open", "exists", "listing"])
def test_any_file_a_check_reads_invalidates_the_cached_outcome(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, read: str
) -> None:
    monkeypatch.setattr(inspection, "file_checks", lambda: [reading_check(read)])
    monkeypatch.setattr(cli, "worker_outcomes", in_process)
    scan: Scan = request.getfixturevalue("scan")
    write(tmp_path, {"app.py": "VALUE = 1\n", "other.py": "VALUE = 2\n"})
    first, _ = scan()
    unchanged, untouched = scan()
    write(tmp_path, {NEIGHBOR: "flag\n"})
    report, inspected = scan()
    assert [finding["check_id"] for finding in first["findings"]] == []
    assert (unchanged, untouched) == (first, [])
    assert inspected == ["app.py", NEIGHBOR, "other.py"]
    assert [finding["check_id"] for finding in report["findings"]] == ["TEST-9", "TEST-9"]
