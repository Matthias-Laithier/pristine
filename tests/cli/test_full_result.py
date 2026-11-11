import json
from collections.abc import Callable, Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from pristine.cli.main import main
from pristine.reports.findings import Finding, Severity
from pristine.reports.outcomes import Checked
from tests.services.secret_scan import gitleaks_without_leaks

EXPECTED_JSON_REPORT = {
    "verification_status": "complete",
    "summary": {
        "errors": 2,
        "warnings": 0,
        "checked_files": 2,
        "unchecked_files": 0,
        "skipped_files": 0,
        "missing_paths": 0,
        "unsupported_files": 0,
        "verification_failures": 0,
        "by_check": {"STR-1": 1, "STR-4": 1},
        "omitted": 0,
    },
    "findings": [
        {
            "path": "invoice.py",
            "line": 1,
            "check_id": "STR-1",
            "severity": "error",
            "message": "invoice file is too long",
        },
        {
            "path": "receipt.py",
            "line": 2,
            "check_id": "STR-4",
            "severity": "error",
            "message": "receipt file has a comment",
        },
    ],
    "triage": [
        {"path": "invoice.py", "distinct_checks": 1, "findings": 1, "fix": {"STR-1": 1}, "verify": {}},
        {"path": "receipt.py", "distinct_checks": 1, "findings": 1, "fix": {"STR-4": 1}, "verify": {}},
    ],
    "unchecked": [],
    "skipped": [],
    "unsupported": [],
    "missing": [],
    "next_step": (
        "Resolve errors and verification gaps. Warnings need judgment. "
        "A clean scan establishes only the patterns listed by pristine checks."
    ),
}


def worker_outcomes(
    stdout: pytest.CaptureFixture[str],
) -> Callable[[list[str], int], AbstractContextManager[Iterator[tuple[str, Checked]]]]:
    findings = [
        Finding("invoice.py", 1, "STR-1", Severity.ERROR, "invoice file is too long"),
        Finding("receipt.py", 2, "STR-4", Severity.ERROR, "receipt file has a comment"),
    ]
    outcomes = iter(
        [
            ("invoice.py", Checked([findings[0]])),
            ("receipt.py", Checked([findings[1]])),
        ]
    )

    @contextmanager
    def outcomes_for(paths: list[str], jobs: int) -> Generator[Iterator[tuple[str, Checked]]]:
        del paths, jobs

        def results() -> Iterator[tuple[str, Checked]]:
            yield next(outcomes)
            captured = stdout.readouterr().out
            assert captured == ""
            yield next(outcomes)

        yield results()

    return outcomes_for


@pytest.mark.parametrize(
    "report_options",
    [("--json",), ()],
    ids=["json", "text"],
)
def test_check_returns_the_full_result_after_every_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    report_options: tuple[str, ...],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "invoice.py").write_text("invoice_total = 1\n", encoding="utf-8")
    (tmp_path / "receipt.py").write_text("receipt_total = 2\n", encoding="utf-8")

    with (
        patch("pristine.services.gitleaks.run_gitleaks", gitleaks_without_leaks),
        patch("pristine.cli.main.worker_outcomes", worker_outcomes(capsys)),
    ):
        assert main(["check", "invoice.py", "receipt.py", "--jobs", "1", *report_options]) == 1

    output = capsys.readouterr().out
    if report_options:
        assert json.loads(output) == EXPECTED_JSON_REPORT
    else:
        assert "invoice.py\n  1 error; fix STR-1\n  - file: STR-1 error: invoice file is too long" in output
        assert "receipt.py\n  1 error; fix STR-4\n  - line 2: STR-4 error: receipt file has a comment" in output
        assert "summary: 2 errors, 0 warnings\nfiles: 2 checked files" in output
        assert "verification: complete, 0 failures" in output


def test_stream_is_not_a_check_option(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["check", ".", "--stream"])

    assert exit_info.value.code == 2
    assert "unrecognized arguments: --stream" in capsys.readouterr().err
