from dataclasses import dataclass

from pristine.reports.findings import Finding


@dataclass(frozen=True)
class Checked:
    findings: list[Finding]


@dataclass(frozen=True)
class Unchecked:
    reason: str


@dataclass(frozen=True)
class Skipped:
    reason: str


type Outcome = Checked | Unchecked | Skipped
