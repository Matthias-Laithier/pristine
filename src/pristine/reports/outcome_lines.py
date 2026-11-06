import json

from pristine.reports.findings import Finding, FindingKind, Severity, finding_record
from pristine.reports.outcomes import Checked, Outcome, Skipped, Unchecked, Unsupported

type ReasonOutcome = Unchecked | Unsupported | Skipped

REASON_OUTCOMES: dict[str, type[ReasonOutcome]] = {
    "unchecked": Unchecked,
    "unsupported": Unsupported,
    "skipped": Skipped,
}
OUTCOME_KINDS: dict[type[ReasonOutcome], str] = {
    Unchecked: "unchecked",
    Unsupported: "unsupported",
    Skipped: "skipped",
}
FINDING_TEXT_FIELDS = ("path", "rule_id", "message")
SEVERITIES = frozenset(Severity)


class MalformedOutcomeLine(ValueError):
    pass


def encoded_outcome(path: str, outcome: Outcome) -> str:
    if isinstance(outcome, Checked):
        body: dict[str, object] = {
            "kind": "checked",
            "findings": [finding_record(finding) for finding in outcome.findings],
        }
    else:
        body = {"kind": OUTCOME_KINDS[type(outcome)], "reason": outcome.reason}
    return json.dumps({"path": path, **body}) + "\n"


def decoded_finding(entry: object) -> Finding:
    if not isinstance(entry, dict):
        raise MalformedOutcomeLine("a finding is not an object")
    path, rule_id, message = (entry.get(field) for field in FINDING_TEXT_FIELDS)
    line, severity = entry.get("line"), entry.get("severity")
    kind = entry.get("kind", FindingKind.CODE)
    has_texts = isinstance(path, str) and isinstance(rule_id, str) and isinstance(message, str)
    has_line = isinstance(line, int) and not isinstance(line, bool)
    if not has_texts or not has_line or severity not in SEVERITIES or kind not in FindingKind:
        raise MalformedOutcomeLine("a finding lacks a path, line, rule, severity, message, or kind")
    return Finding(path, line, rule_id, Severity(severity), message, FindingKind(kind))


def decoded_body(document: dict[str, object]) -> Outcome:
    kind, reason, findings = document.get("kind"), document.get("reason"), document.get("findings")
    if kind == "checked" and isinstance(findings, list):
        return Checked([decoded_finding(entry) for entry in findings])
    if isinstance(kind, str) and kind in REASON_OUTCOMES and isinstance(reason, str):
        return REASON_OUTCOMES[kind](reason)
    raise MalformedOutcomeLine("the outcome has no known kind with its fields")


def decoded_outcome(line: str) -> tuple[str, Outcome]:
    try:
        document = json.loads(line)
    except json.JSONDecodeError as error:
        raise MalformedOutcomeLine("the line is not JSON") from error
    path = document.get("path") if isinstance(document, dict) else None
    if not isinstance(path, str):
        raise MalformedOutcomeLine("the line is not an object with a path")
    return path, decoded_body(document)
