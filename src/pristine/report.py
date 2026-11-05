from collections import Counter
from dataclasses import dataclass

from pristine.findings import Finding, Severity
from pristine.outcomes import Checked, Outcome, Skipped, Unchecked


@dataclass(frozen=True)
class Report:
    findings: list[Finding]
    unchecked: dict[str, str]
    skipped: dict[str, str]
    checked_files: int
    missing: tuple[str, ...]

    def count(self, severity: Severity) -> int:
        return sum(1 for finding in self.findings if finding.severity is severity)

    def by_rule(self) -> dict[str, int]:
        counts = Counter(finding.rule_id for finding in self.findings)
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def build_report(outcomes: dict[str, Outcome], path_findings: list[Finding], missing: tuple[str, ...] = ()) -> Report:
    ordered = sorted(outcomes.items())
    file_findings = [finding for _, outcome in ordered if isinstance(outcome, Checked) for finding in outcome.findings]
    findings = sorted(
        [*file_findings, *path_findings], key=lambda finding: (finding.path, finding.line, finding.rule_id)
    )
    unchecked = {path: outcome.reason for path, outcome in ordered if isinstance(outcome, Unchecked)}
    skipped = {path: outcome.reason for path, outcome in ordered if isinstance(outcome, Skipped)}
    checked_files = len(outcomes) - len(unchecked) - len(skipped)
    return Report(findings, unchecked, skipped, checked_files, missing)
