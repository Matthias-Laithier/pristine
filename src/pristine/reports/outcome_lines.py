import json

from pristine.reports.findings import Finding, FindingKind, Severity, finding_record
from pristine.reports.outcomes import Checked, FileRead, Outcome, Signature, Skipped, Unchecked, Unsupported

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
FINDING_TEXT_FIELDS = ("path", "check_id", "message")
SEVERITIES = frozenset(Severity)
SIGNATURE_FIELDS = 5


class MalformedOutcomeLine(ValueError):
    pass


def encoded_outcome(path: str, outcome: Outcome) -> str:
    return json.dumps({"path": path, **outcome_record(outcome)}) + "\n"


def checked_record(outcome: Checked) -> dict[str, object]:
    record: dict[str, object] = {"kind": "checked", "findings": [finding_record(item) for item in outcome.findings]}
    if outcome.reads is not None:
        record["reads"] = {path: read_record(read) for path, read in outcome.reads.items()}
    return record


def outcome_record(outcome: Outcome) -> dict[str, object]:
    if isinstance(outcome, Checked):
        return checked_record(outcome)
    return {"kind": OUTCOME_KINDS[type(outcome)], "reason": outcome.reason}


def read_record(read: FileRead) -> dict[str, object]:
    return {"listed": read.listed, "digest": read.digest, "signature": read.signature}


def decoded_signature(value: object) -> Signature | None:
    if value is None:
        return None
    items: list[object] = list(value) if isinstance(value, list) else []
    numbers = [item for item in items if isinstance(item, int) and not isinstance(item, bool)]
    if len(items) != SIGNATURE_FIELDS or len(numbers) != SIGNATURE_FIELDS:
        raise MalformedOutcomeLine("a file read signature is not five integers")
    device, inode, size, modified, changed = numbers
    return device, inode, size, modified, changed


def decoded_read(entry: object) -> FileRead:
    listed, digest = (entry.get("listed"), entry.get("digest")) if isinstance(entry, dict) else (None, None)
    if not isinstance(entry, dict) or not isinstance(listed, bool) or not isinstance(digest, str):
        raise MalformedOutcomeLine("a file read lacks its listing flag or digest")
    return FileRead(listed, digest, decoded_signature(entry.get("signature")))


def decoded_reads(reads: object) -> dict[str, FileRead] | None:
    if reads is None:
        return None
    if not isinstance(reads, dict) or not all(isinstance(path, str) for path in reads):
        raise MalformedOutcomeLine("the file reads are not keyed by path")
    return {path: decoded_read(entry) for path, entry in reads.items()}


def decoded_finding(entry: object) -> Finding:
    if not isinstance(entry, dict):
        raise MalformedOutcomeLine("a finding is not an object")
    path, check_id, message = (entry.get(field) for field in FINDING_TEXT_FIELDS)
    line, severity = entry.get("line"), entry.get("severity")
    kind = entry.get("kind", FindingKind.CODE)
    has_texts = isinstance(path, str) and isinstance(check_id, str) and isinstance(message, str)
    has_line = isinstance(line, int) and not isinstance(line, bool)
    has_severity = isinstance(severity, str) and severity in SEVERITIES
    if not has_texts or not has_line or not has_severity or kind not in FindingKind:
        raise MalformedOutcomeLine("a finding lacks a path, line, check ID, severity, message, or kind")
    return Finding(path, line, check_id, Severity(severity), message, FindingKind(kind))


def decoded_body(document: dict[str, object]) -> Outcome:
    kind, reason, findings = document.get("kind"), document.get("reason"), document.get("findings")
    if kind == "checked" and isinstance(findings, list):
        return Checked([decoded_finding(entry) for entry in findings], decoded_reads(document.get("reads")))
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
