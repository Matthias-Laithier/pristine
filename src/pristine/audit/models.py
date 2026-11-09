from dataclasses import dataclass

__all__ = ["AuditReport", "DependencyFinding", "SourceEvidence"]


@dataclass(frozen=True)
class DependencyFinding:
    source_path: str
    source_type: str
    package: str
    version: str
    ecosystem: str
    advisory_id: str
    aliases: tuple[str, ...]
    fixed_versions: tuple[str, ...]


@dataclass(frozen=True)
class SourceEvidence:
    path: str
    source_type: str
    package_count: int


@dataclass(frozen=True)
class AuditReport:
    findings: tuple[DependencyFinding, ...]
    sources: tuple[SourceEvidence, ...]
    problems: tuple[str, ...]

    @property
    def verification_failed(self) -> bool:
        return bool(self.problems) or not any(source.package_count > 0 for source in self.sources)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "advisory_records": len(self.findings),
            "packages": sum(source.package_count for source in self.sources),
            "sources": len(self.sources),
            "verification_failures": max(len(self.problems), int(self.verification_failed)),
        }
