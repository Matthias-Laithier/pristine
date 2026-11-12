from dataclasses import dataclass, field

from pristine.reports.findings import Finding

type Signature = tuple[int, int, int, int, int]


@dataclass(frozen=True)
class FileRead:
    listed: bool
    digest: str
    signature: Signature | None


@dataclass(frozen=True)
class Checked:
    findings: list[Finding]
    reads: dict[str, FileRead] | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Unchecked:
    reason: str


@dataclass(frozen=True)
class Unsupported:
    reason: str


@dataclass(frozen=True)
class Skipped:
    reason: str


type Outcome = Checked | Unchecked | Unsupported | Skipped
