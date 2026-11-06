from typing import NotRequired, TypedDict


class ReportedFinding(TypedDict):
    path: str
    line: int
    rule_id: str
    severity: str
    message: str
    kind: NotRequired[str]


class ReportedPath(TypedDict):
    path: str
    reason: str


class ReportSummary(TypedDict):
    errors: int
    warnings: int
    checked_files: int
    unchecked_files: int
    skipped_files: int
    missing_paths: int
    unsupported_files: NotRequired[int]
    verification_failures: NotRequired[int]
    by_rule: dict[str, int]
    omitted: int


class JsonReport(TypedDict):
    summary: ReportSummary
    findings: list[ReportedFinding]
    unchecked: list[ReportedPath]
    skipped: list[ReportedPath]
    missing: list[str]
    verification_status: NotRequired[str]
    unsupported: NotRequired[list[str]]
