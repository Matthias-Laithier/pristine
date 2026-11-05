import sys

import pytest

from pristine.findings import Finding, Severity
from pristine.outcome_lines import MalformedOutcomeLine, decoded_outcome, encoded_outcome
from pristine.outcomes import Checked, Outcome, Skipped, Unchecked
from pristine.services.isolated_inspection import LOST_FILE_REASON, decoded_results, inspect_in_workers

CRASHING_WORKER = (
    "import os, sys\n"
    "from pristine.outcome_lines import encoded_outcome\n"
    "from pristine.outcomes import Checked\n"
    "for path in sys.stdin.buffer.read().decode().split('\\0'):\n"
    "    if path == 'crash.py':\n"
    '        sys.stdout.write(\'{"path": "crash.py", "kind": "chec\')\n'
    "        sys.stdout.flush()\n"
    "        os.abort()\n"
    "    sys.stdout.write(encoded_outcome(path, Checked([])))\n"
    "    sys.stdout.flush()\n"
)
INVOICE_FINDING = Finding("invoices.py", 3, "CR-3", Severity.WARNING, "comment")


def test_a_crashing_file_is_unchecked_and_the_others_still_run() -> None:
    paths = ["a.py", "crash.py", "b.py"]
    outcomes = inspect_in_workers(paths, command=(sys.executable, "-c", CRASHING_WORKER))
    assert outcomes == {"a.py": Checked([]), "crash.py": Unchecked(LOST_FILE_REASON), "b.py": Checked([])}


@pytest.mark.parametrize(
    "outcome", [Checked([INVOICE_FINDING]), Checked([]), Unchecked("no grammar"), Skipped("generated file")]
)
def test_every_outcome_survives_its_json_line(outcome: Outcome) -> None:
    assert decoded_outcome(encoded_outcome("invoices.py", outcome)) == ("invoices.py", outcome)


@pytest.mark.parametrize(
    "line",
    [
        "",
        "[]",
        '{"kind": "skipped", "reason": "lockfile"}',
        '{"path": "a.py", "kind": "lost", "reason": "lockfile"}',
        '{"path": "a.py", "kind": "checked", "findings": [{"path": "a.py", "line": true}]}',
        (
            '{"path": "a.py", "kind": "checked", "findings": [{"path": "a.py", "line": 1, "rule_id": "CR-3", '
            '"severity": "fatal", "message": "comment"}]}'
        ),
    ],
)
def test_a_malformed_line_is_rejected(line: str) -> None:
    with pytest.raises(MalformedOutcomeLine):
        decoded_outcome(line)


def test_malformed_lines_count_as_not_reported() -> None:
    output = ("not json\n" + encoded_outcome("a.py", Skipped("lockfile"))).encode()
    assert decoded_results(output) == {"a.py": Skipped("lockfile")}
