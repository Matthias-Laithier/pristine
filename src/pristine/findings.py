from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule_id: str
    severity: Severity
    message: str


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
