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
        "by_rule": {"CR-1": 1, "CR-3": 1},
        "omitted": 0,
    },
    "findings": [
        {
            "path": "invoice.py",
            "line": 1,
            "rule_id": "CR-1",
            "severity": "error",
            "message": "invoice file is too long",
        },
        {
            "path": "receipt.py",
            "line": 2,
            "rule_id": "CR-3",
            "severity": "error",
            "message": "receipt file has a comment",
        },
    ],
    "triage": [
        {"path": "invoice.py", "distinct_rules": 1, "findings": 1, "fix": {"CR-1": 1}, "verify": {}},
        {"path": "receipt.py", "distinct_rules": 1, "findings": 1, "fix": {"CR-3": 1}, "verify": {}},
    ],
    "unchecked": [],
    "skipped": [],
    "unsupported": [],
    "missing": [],
    "next_step": (
        "next: fix every finding or report it by rule ID as a deliberate break with its reason. "
        "Read a rule in full with 'pristine rule <ID>' when a finding cites it. "
        "Before finishing, review your change against every review rule it touches, listed in 'pristine guide'. "
        "Checks cover only the mechanical part of the checked rules."
    ),
}


def worker_outcomes(
    stdout: pytest.CaptureFixture[str],
) -> Callable[[list[str], int], AbstractContextManager[Iterator[tuple[str, Checked]]]]:
    findings = [
        Finding("invoice.py", 1, "CR-1", Severity.ERROR, "invoice file is too long"),
        Finding("receipt.py", 2, "CR-3", Severity.ERROR, "receipt file has a comment"),
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
        assert "invoice.py\n  1 error; fix CR-1\n  - file: CR-1 error: invoice file is too long" in output
        assert "receipt.py\n  1 error; fix CR-3\n  - line 2: CR-3 error: receipt file has a comment" in output
        assert "summary: 2 errors, 0 warnings\nfiles: 2 checked files" in output
        assert "verification: complete, 0 failures" in output


def test_stream_is_not_a_check_option(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["check", ".", "--stream"])

    assert exit_info.value.code == 2
    assert "unrecognized arguments: --stream" in capsys.readouterr().err
