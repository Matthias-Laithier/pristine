import json
from collections import Counter

from pristine.reports.findings import Finding, FindingKind, Severity, finding_record
from pristine.reports.report import Report
from pristine.reports.triage import FileTriage, ranked_files

_FILE_LEVEL_RULES = frozenset({"CR-1", "CR-9", "CR-15", "CO-14", "TL-1"})
_FILE_LEVEL_FIRST_LINE_RULES = frozenset({"TL-3", "TL-4"})
NEXT_STEP = (
    "next: fix every finding or report it by rule ID as a deliberate break with its reason. "
    "Read a rule in full with 'pristine rule <ID>' when a finding cites it. "
    "Before finishing, review your change against every review rule it touches, listed in 'pristine guide'. "
    "Checks cover only the mechanical part of the checked rules."
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
    omitted = len(report.findings) - len(shown)
    document = {
        "verification_status": "incomplete" if report.verification_failed else "complete",
        "summary": json_summary(report, omitted),
        "findings": [finding_record(finding) for finding in shown],
        "triage": [_triage_record(file) for file in ranked_files(report.findings)],
        "unchecked": [{"path": path, "reason": reason} for path, reason in report.unchecked.items()],
        "skipped": [{"path": path, "reason": reason} for path, reason in report.skipped.items()],
        "unsupported": list(report.unsupported),
        "missing": report.missing,
        "next_step": NEXT_STEP,
    }
    return json.dumps(document, indent=2)


def json_summary(report: Report, omitted: int) -> dict[str, object]:
    return {
        **summary(report),
        "unsupported_files": len(report.unsupported),
        "verification_failures": report.verification_failures,
        "by_rule": report.by_rule(),
        "omitted": omitted,
    }


def render_text(report: Report, limit: int | None) -> str:
    lines = _render_triage(report, limit)
    lines += [f"missing: {path}" for path in report.missing]
    lines += [f"unchecked: {path} ({reason})" for path, reason in report.unchecked.items()]
    skipped_reasons = Counter(report.skipped.values())
    lines += [f"skipped: {counted(count, 'file')}, {reason}" for reason, count in sorted(skipped_reasons.items())]
    if lines:
        lines.append("")
    lines += _render_summary(report)
    lines += ["", *_review_guidance()]
    return "\n".join(lines)


def _render_summary(report: Report) -> list[str]:
    counts = summary(report)
    groups = (
        ("summary", ("errors", "warnings")),
        ("files", ("checked_files", "unchecked_files", "skipped_files", "missing_paths")),
    )
    lines = ["Mechanical checks"] + [
        f"{label}: " + ", ".join(counted(counts[key], key.replace("_", " ").removesuffix("s")) for key in keys)
        for label, keys in groups
    ]
    if report.findings:
        lines.append("by rule: " + ", ".join(f"{rule_id} {count}" for rule_id, count in report.by_rule().items()))
    lines.append(
        "verification: "
        + ("incomplete" if report.verification_failed else "complete")
        + f", {report.verification_failures} failures"
    )
    return lines


def _review_guidance() -> list[str]:
    sentences = NEXT_STEP.removeprefix("next: ").split(". ")
    return ["Required agent review", *(f"  - {sentence.rstrip('.')}." for sentence in sentences)]


def _triage_record(file: FileTriage) -> dict[str, object]:
    return {
        "path": file.path,
        "distinct_rules": file.distinct_rules,
        "findings": len(file.findings),
        "fix": file.by_rule(FindingKind.CODE),
        "verify": file.by_rule(FindingKind.VERIFICATION),
    }


def _file_overview(file: FileTriage) -> str:
    severity_counts = Counter(finding.severity for finding in file.findings)
    overview = [
        ", ".join(counted(severity_counts[severity], severity) for severity in Severity if severity_counts[severity])
    ]
    if rules := file.by_rule(FindingKind.CODE):
        overview.append("fix " + ", ".join(rules))
    if rules := file.by_rule(FindingKind.VERIFICATION):
        overview.append("verify " + ", ".join(rules))
    return f"{file.path}\n  " + "; ".join(overview)


def _render_finding(finding: Finding) -> str:
    file_level = (
        finding.line <= 0
        or finding.rule_id in _FILE_LEVEL_RULES
        or (
            finding.line == 1
            and (finding.kind is FindingKind.VERIFICATION or finding.rule_id in _FILE_LEVEL_FIRST_LINE_RULES)
        )
    )
    location = "file" if file_level else f"line {finding.line}"
    action = "verify " if finding.kind is FindingKind.VERIFICATION else ""
    return f"  - {location}: {action}{finding.rule_id} {finding.severity}: {finding.message}"


def _render_triage(report: Report, limit: int | None) -> list[str]:
    if not report.findings:
        return []
    lines: list[str] = ["Findings (ranked by distinct code rules, then path)"]
    remaining = len(report.findings) if limit is None else limit
    omitted: Counter[str] = Counter()
    for file in ranked_files(report.findings):
        shown = file.findings[:remaining]
        remaining -= len(shown)
        lines += ["", _file_overview(file)]
        lines.extend(_render_finding(finding) for finding in shown)
        omitted.update(finding.rule_id for finding in file.findings[len(shown) :])
    if omitted:
        omitted_rules = ", ".join(f"{rule_id} {count}" for rule_id, count in sorted(omitted.items()))
        advice = "raise --max or remove --max to see them all"
        lines.append(f"... {counted(sum(omitted.values()), 'more finding')} omitted ({omitted_rules}); {advice}")
    return lines
