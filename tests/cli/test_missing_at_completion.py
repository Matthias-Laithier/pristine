import json
from collections.abc import Callable, Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from pristine.cli.main import main
from pristine.reports.outcomes import Checked
from tests.services.secret_scan import gitleaks_without_leaks


def worker_that_deletes_invoice(
    tmp_path: Path,
) -> Callable[[list[str], int], AbstractContextManager[Iterator[tuple[str, Checked]]]]:
    @contextmanager
    def outcomes_for(paths: list[str], jobs: int) -> Generator[Iterator[tuple[str, Checked]]]:
        del paths, jobs

        def outcomes() -> Iterator[tuple[str, Checked]]:
            yield "invoice.py", Checked([])
            (tmp_path / "invoice.py").unlink()
            yield "receipt.py", Checked([])

        yield outcomes()

    return outcomes_for


def test_paths_removed_during_workers_are_missing_at_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "invoice.py").write_text("invoice_total = 1\n", encoding="utf-8")
    (tmp_path / "receipt.py").write_text("receipt_total = 1\n", encoding="utf-8")

    with (
        patch("pristine.services.gitleaks.run_gitleaks", gitleaks_without_leaks),
        patch("pristine.cli.main.worker_outcomes", worker_that_deletes_invoice(tmp_path)),
    ):
        assert main(["check", "invoice.py", "receipt.py", "--jobs", "1", "--json"]) == 0

    document = json.loads(capsys.readouterr().out)
    assert document["missing"] == ["invoice.py"]
    assert document["summary"]["missing_paths"] == 1
