import json
from dataclasses import asdict

from pristine.findings import Finding, Severity
from pristine.outcomes import Checked, Outcome, Skipped, Unchecked

REASON_OUTCOMES: dict[str, type[Unchecked] | type[Skipped]] = {"unchecked": Unchecked, "skipped": Skipped}
FINDING_TEXT_FIELDS = ("path", "rule_id", "message")
SEVERITIES = frozenset(Severity)


class MalformedOutcomeLine(ValueError):
    pass


def encoded_outcome(path: str, outcome: Outcome) -> str:
    if isinstance(outcome, Checked):
        body: dict[str, object] = {"kind": "checked", "findings": [asdict(finding) for finding in outcome.findings]}
    else:
        body = {"kind": "unchecked" if isinstance(outcome, Unchecked) else "skipped", "reason": outcome.reason}
    return json.dumps({"path": path, **body}) + "\n"


def decoded_finding(entry: object) -> Finding:
    if not isinstance(entry, dict):
        raise MalformedOutcomeLine("a finding is not an object")
    path, rule_id, message = (entry.get(field) for field in FINDING_TEXT_FIELDS)
    line, severity = entry.get("line"), entry.get("severity")
    has_texts = isinstance(path, str) and isinstance(rule_id, str) and isinstance(message, str)
    has_line = isinstance(line, int) and not isinstance(line, bool)
    if not has_texts or not has_line or severity not in SEVERITIES:
        raise MalformedOutcomeLine("a finding lacks a path, line, rule, severity, or message")
    return Finding(path, line, rule_id, Severity(severity), message)


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
