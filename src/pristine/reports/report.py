from collections import Counter
from dataclasses import dataclass, field

from pristine.reports.findings import Finding, FindingKind, Severity
from pristine.reports.outcomes import Checked, Outcome, Skipped, Unchecked, Unsupported


@dataclass(frozen=True)
class Report:
    findings: list[Finding]
    unchecked: dict[str, str]
    skipped: dict[str, str]
    checked_files: int
    missing: tuple[str, ...]
    unsupported: dict[str, str] = field(default_factory=dict)

    def count(self, severity: Severity) -> int:
        return sum(1 for finding in self.findings if finding.severity is severity)

    def by_check(self) -> dict[str, int]:
        counts = Counter(finding.check_id for finding in self.findings)
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    @property
    def verification_failures(self) -> int:
        genuine_unchecked = sum(path not in self.unsupported for path in self.unchecked)
        verification_findings = sum(finding.kind is FindingKind.VERIFICATION for finding in self.findings)
        return genuine_unchecked + verification_findings

    @property
    def verification_failed(self) -> bool:
        return bool(self.verification_failures)

    def __post_init__(self) -> None:
        if not self.unsupported.items() <= self.unchecked.items():
            raise ValueError("every unsupported path must also be unchecked")


def build_report(outcomes: dict[str, Outcome], path_findings: list[Finding], missing: tuple[str, ...] = ()) -> Report:
    ordered = sorted(outcomes.items())
    file_findings = [finding for _, outcome in ordered if isinstance(outcome, Checked) for finding in outcome.findings]
    findings = sorted(
        [*file_findings, *path_findings], key=lambda finding: (finding.path, finding.line, finding.check_id)
    )
    unchecked = {path: outcome.reason for path, outcome in ordered if isinstance(outcome, Unchecked | Unsupported)}
    unsupported = {path: outcome.reason for path, outcome in ordered if isinstance(outcome, Unsupported)}
    skipped = {path: outcome.reason for path, outcome in ordered if isinstance(outcome, Skipped)}
    checked_files = len(outcomes) - len(unchecked) - len(skipped)
    return Report(findings, unchecked, skipped, checked_files, missing, unsupported)
