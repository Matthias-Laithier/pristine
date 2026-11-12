from collections.abc import Callable, Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

import pytest

from pristine.cli import main as cli
from pristine.reports.outcomes import Outcome
from tests.conftest import parsed_report
from tests.report_types import JsonReport

type Workers = Callable[[list[str], int], AbstractContextManager[Iterator[tuple[str, Outcome]]]]
type Scan = Callable[..., tuple[JsonReport, list[str]]]


def counting(workers: Workers, inspected: list[str]) -> Workers:
    @contextmanager
    def outcomes(paths: list[str], jobs: int) -> Generator[Iterator[tuple[str, Outcome]]]:
        inspected.extend(paths)
        with workers(paths, jobs) as completed:
            yield completed

    return outcomes


@pytest.fixture
def scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> Scan:
    monkeypatch.chdir(tmp_path)
    real_workers = cli.worker_outcomes

    def run(*options: str) -> tuple[JsonReport, list[str]]:
        inspected: list[str] = []
        monkeypatch.setattr(cli, "worker_outcomes", counting(real_workers, inspected))
        cli.main(["check", ".", "--json", "--jobs", "1", *options])
        return parsed_report(capsys.readouterr().out), sorted(inspected)

    return run


def write(root: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(content)
