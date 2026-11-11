from collections import Counter
from dataclasses import dataclass

from pristine.reports.findings import Finding, FindingKind

__all__ = ["FileTriage", "ranked_files"]


@dataclass(frozen=True)
class FileTriage:
    path: str
    findings: tuple[Finding, ...]

    def by_check(self, kind: FindingKind) -> dict[str, int]:
        counts = Counter(finding.check_id for finding in self.findings if finding.kind is kind)
        return dict(sorted(counts.items()))

    @property
    def distinct_checks(self) -> int:
        return len(self.by_check(FindingKind.CODE))


def ranked_files(findings: list[Finding]) -> list[FileTriage]:
    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(finding.path, []).append(finding)
    files = [FileTriage(path, tuple(entries)) for path, entries in grouped.items()]
    return sorted(files, key=lambda file: (-file.distinct_checks, file.path))
