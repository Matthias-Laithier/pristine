import json
from collections import Counter

from pristine.reports.findings import Severity, finding_record
from pristine.reports.report import Report

NEXT_STEP = (
    "next: fix every finding, or report it by rule ID as a deliberate break with its reason. "
    "This check favors precision over recall: a clean result proves nothing about the rules it cannot "
    "decide, so review your change against every relevant rule yourself."
)


def counted(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def summary(report: Report) -> dict[str, int]:
    return {
        "errors": report.count(Severity.ERROR),
        "warnings": report.count(Severity.WARNING),
        "checked_files": report.checked_files,
        "unchecked_files": len(report.unchecked),
        "skipped_files": len(report.skipped),
        "missing_paths": len(report.missing),
    }


def render_json(report: Report, limit: int | None) -> str:
    shown = report.findings[:limit]
    document = {
        "verification_status": "incomplete" if report.verification_failed else "complete",
        "summary": {
            **summary(report),
            "unsupported_files": len(report.unsupported),
            "verification_failures": report.verification_failures,
            "by_rule": report.by_rule(),
            "omitted": len(report.findings) - len(shown),
        },
        "findings": [finding_record(finding) for finding in shown],
        "unchecked": [{"path": path, "reason": reason} for path, reason in report.unchecked.items()],
        "skipped": [{"path": path, "reason": reason} for path, reason in report.skipped.items()],
        "unsupported": list(report.unsupported),
        "missing": report.missing,
    }
    return json.dumps(document, indent=2)


def render_text(report: Report, limit: int | None) -> str:
    shown = report.findings[:limit]
    lines = [
        f"{finding.path}:{finding.line}: {finding.rule_id} {finding.severity}: {finding.message}" for finding in shown
    ]
    if len(shown) < len(report.findings):
        lines.append(
            f"... {counted(len(report.findings) - len(shown), 'more finding')} omitted, raise --max or use --json to see them"
        )
    lines += [f"missing: {path}" for path in report.missing]
    lines += [f"unchecked: {path} ({reason})" for path, reason in report.unchecked.items()]
    skipped_reasons = Counter(report.skipped.values())
    lines += [f"skipped: {counted(count, 'file')}, {reason}" for reason, count in sorted(skipped_reasons.items())]
    lines.append(
        "summary: "
        + ", ".join(counted(value, key.replace("_", " ").removesuffix("s")) for key, value in summary(report).items())
    )
    if report.findings:
        lines.append("by rule: " + ", ".join(f"{rule_id} {count}" for rule_id, count in report.by_rule().items()))
    lines.append(
        "verification: "
        + ("incomplete" if report.verification_failed else "complete")
        + f", {report.verification_failures} failures"
    )
    lines.append(NEXT_STEP)
    return "\n".join(lines)
