from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class FindingKind(StrEnum):
    CODE = "code"
    VERIFICATION = "verification"


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    check_id: str
    severity: Severity
    message: str
    kind: FindingKind = FindingKind.CODE


def finding_record(finding: Finding) -> dict[str, object]:
    record: dict[str, object] = {
        "path": finding.path,
        "line": finding.line,
        "check_id": finding.check_id,
        "severity": finding.severity,
        "message": finding.message,
    }
    if finding.kind is not FindingKind.CODE:
        record["kind"] = finding.kind
    return record


@dataclass(frozen=True)
class Limit:
    target: int
    hard: int

    def severity_for(self, measured: int) -> Severity | None:
        if measured > self.hard:
            return Severity.ERROR
        if measured > self.target:
            return Severity.WARNING
        return None

    def describe(self) -> str:
        return f"target {self.target}, hard limit {self.hard}"
