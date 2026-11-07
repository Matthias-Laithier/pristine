import json

from pristine.cli.rendering import json_summary
from pristine.reports.findings import Finding, finding_record
from pristine.reports.outcome_lines import outcome_record
from pristine.reports.outcomes import Outcome
from pristine.reports.report import Report


def encode_event(**event: object) -> str:
    return json.dumps(event, separators=(",", ":"))


def stream_path_findings(path_findings: list[Finding]) -> str:
    return encode_event(
        event="path_findings",
        phase="provisional",
        findings=[finding_record(finding) for finding in path_findings],
    )


def stream_file_outcome(path: str, outcome: Outcome) -> str:
    return encode_event(
        event="file_outcome",
        phase="provisional",
        path=path,
        outcome=outcome_record(outcome),
    )


def stream_complete(report: Report) -> str:
    return encode_event(
        event="complete",
        phase="complete",
        verification_status="incomplete" if report.verification_failed else "complete",
        summary=json_summary(report, 0),
        missing=report.missing,
    )
