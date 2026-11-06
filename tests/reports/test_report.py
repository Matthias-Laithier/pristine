import json

from pristine.cli.rendering import render_json
from pristine.reports.findings import Finding, FindingKind, Severity
from pristine.reports.outcome_lines import decoded_outcome, encoded_outcome
from pristine.reports.outcomes import Checked, Skipped, Unchecked, Unsupported
from pristine.reports.report import build_report


def test_report_renders_additive_verification_fields() -> None:
    code_finding = Finding("invoice.py", 3, "CR-3", Severity.WARNING, "comment")
    verification_finding = Finding(
        "verification.py",
        1,
        "CR-3",
        Severity.ERROR,
        "not verified",
        FindingKind.VERIFICATION,
    )
    outcomes = {
        "invoice.py": Checked([code_finding]),
        "verification.py": Checked([verification_finding]),
        "lost.py": Unchecked("parser crashed"),
        "archive.zip": Unsupported("binary archive"),
        "lock.json": Skipped("lockfile"),
    }
    report = build_report(outcomes, [], ("gone.py",))

    assert report.checked_files == 2
    assert report.unchecked == {"lost.py": "parser crashed", "archive.zip": "binary archive"}
    assert report.unsupported == {"archive.zip": "binary archive"}
    assert (report.verification_failures, report.verification_failed) == (2, True)

    document = json.loads(render_json(report, None))
    assert document["verification_status"] == "incomplete"
    assert document["unsupported"] == ["archive.zip"]
    assert document["findings"][1]["kind"] == "verification"
    assert "kind" not in document["findings"][0]
    assert (document["summary"]["unsupported_files"], document["summary"]["verification_failures"]) == (1, 2)


def test_codec_round_trips_unsupported_and_decodes_legacy_findings() -> None:
    assert decoded_outcome(encoded_outcome("archive.zip", Unsupported("binary archive"))) == (
        "archive.zip",
        Unsupported("binary archive"),
    )
    legacy_line = (
        '{"path": "invoice.py", "kind": "checked", "findings": '
        '[{"path": "invoice.py", "line": 3, "rule_id": "CR-3", "severity": "warning", "message": "comment"}]}'
    )
    expected = Checked([Finding("invoice.py", 3, "CR-3", Severity.WARNING, "comment")])
    assert decoded_outcome(legacy_line) == ("invoice.py", expected)
