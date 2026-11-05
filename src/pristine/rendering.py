import json
from collections import Counter
from dataclasses import asdict

from pristine.checks.registry import file_checks, path_checks
from pristine.findings import Severity
from pristine.project.inspection import PROJECT_RULE_SUMMARIES
from pristine.report import Report
from pristine.rule_documents import RuleDocument, rule_documents

NEXT_STEP = (
    "next: fix every finding, or report it by rule ID as a deliberate break with its reason. "
    "Unchecked files and every rule this tool cannot check still need your own review against the coding rules."
)
REVIEW = "review"
RULES_NEXT_STEP = (
    "next: read a rule with 'pristine rule <ID>'. Rules marked (review) have no automated check: review your "
    "code against them yourself."
)


def summary(report: Report) -> dict[str, int]:
    return {
        "errors": report.count(Severity.ERROR),
        "warnings": report.count(Severity.WARNING),
        "checked_files": report.checked_files,
        "unchecked_files": len(report.unchecked),
        "skipped_files": len(report.skipped),
    }


def render_json(report: Report) -> str:
    document = {
        "summary": summary(report),
        "findings": [asdict(finding) for finding in report.findings],
        "unchecked": [{"path": path, "reason": reason} for path, reason in report.unchecked.items()],
        "skipped": [{"path": path, "reason": reason} for path, reason in report.skipped.items()],
    }
    return json.dumps(document, indent=2)


def render_text(report: Report) -> str:
    lines = [
        f"{finding.path}:{finding.line}: {finding.rule_id} {finding.severity}: {finding.message}"
        for finding in report.findings
    ]
    lines += [f"unchecked: {path} ({reason})" for path, reason in report.unchecked.items()]
    skipped_reasons = Counter(report.skipped.values())
    lines += [f"skipped: {count} file(s), {reason}" for reason, count in sorted(skipped_reasons.items())]
    lines.append("summary: " + ", ".join(f"{value} {key.replace('_', ' ')}" for key, value in summary(report).items()))
    lines.append(NEXT_STEP)
    return "\n".join(lines)


def check_summaries() -> dict[str, tuple[str, str]]:
    checked = {check.rule_id: ("check", check.summary) for check in [*file_checks(), *path_checks()]}
    projected = {rule_id: ("project", summary) for rule_id, summary in PROJECT_RULE_SUMMARIES.items()}
    return checked | projected


def rule_entry(document: RuleDocument, summaries: dict[str, tuple[str, str]]) -> dict[str, str | None]:
    checked_by, summary = summaries.get(document.rule_id, (REVIEW, None))
    return {"rule_id": document.rule_id, "title": document.title, "checked_by": checked_by, "summary": summary}


def rule_entries() -> list[dict[str, str | None]]:
    summaries = check_summaries()
    return [rule_entry(document, summaries) for document in rule_documents()]


def render_rules_json() -> str:
    return json.dumps(rule_entries(), indent=2)


def render_rule_line(entry: dict[str, str | None]) -> str:
    line = f"{entry['rule_id']} {entry['title']} ({entry['checked_by']})"
    return f"{line}: {entry['summary']}" if entry["summary"] else line


def render_rules_text() -> str:
    return "\n".join(map(render_rule_line, rule_entries())) + "\n" + RULES_NEXT_STEP
