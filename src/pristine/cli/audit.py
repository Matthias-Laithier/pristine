import json
from collections import Counter
from dataclasses import asdict

from pristine.audit.models import AuditReport, DependencyFinding
from pristine.cli.rendering import NEXT_STEP, counted

__all__ = ["render_json", "render_text"]

SCOPE = (
    "Native-extracted PyPI package/version known-advisory matches only; no installed-dependency, package-origin, "
    "full-project, or exploitability assurance. Fixed versions are contextual advisory releases, not upgrade recommendations."
)
TEXT_SCOPE = (
    "Scope: known-advisory matches in native uv.lock/PyPI records; no installed/origin/project/exploitability assurance.\n"
    "Fixed releases are advisory context, not upgrade recommendations."
)


def render_json(report: AuditReport, limit: int | None) -> str:
    shown = report.findings[:limit]
    return json.dumps(
        {
            "scope": SCOPE,
            "verification_status": "incomplete" if report.verification_failed else "complete",
            "summary": {**report.counts, "omitted": len(report.findings) - len(shown)},
            "findings": [asdict(finding) for finding in shown],
            "sources": [asdict(source) for source in report.sources],
            "problems": report.problems,
            "next_step": NEXT_STEP,
        },
        indent=2,
    )


def render_text(report: AuditReport, limit: int | None) -> str:
    shown = report.findings[:limit]
    lines = ["Dependency audit", TEXT_SCOPE, *_source_sections(report, shown)]
    omitted = len(report.findings) - len(shown)
    if omitted:
        lines.append(f"... {omitted} findings omitted; raise --max or remove --max to see them all")
    lines.extend(f"verify: {problem}" for problem in report.problems)
    if not report.verification_failed and not report.findings:
        lines.append("No known advisory matches; not proof of security.")
    lines.append("summary: " + ", ".join(f"{count} {name.replace('_', ' ')}" for name, count in report.counts.items()))
    lines.append("verification: " + ("incomplete" if report.verification_failed else "complete"))
    lines.extend(["", "Required agent review"])
    lines.extend(f"  - {sentence.rstrip('.')}." for sentence in NEXT_STEP.removeprefix("next: ").split(". "))
    return "\n".join(lines)


def _finding_line(finding: DependencyFinding) -> str:
    details = [finding.advisory_id]
    if finding.aliases:
        details.append("aliases: " + ", ".join(finding.aliases))
    details.append("fixed releases: " + (", ".join(finding.fixed_versions) or "not reported"))
    return "    - " + "; ".join(details)


def _source_sections(report: AuditReport, shown: tuple[DependencyFinding, ...]) -> list[str]:
    packages: Counter[tuple[str, str]] = Counter()
    for source in report.sources:
        packages[source.path, source.source_type] += source.package_count
    records: Counter[tuple[str, str]] = Counter(
        (finding.source_path, finding.source_type) for finding in report.findings
    )
    lines: list[str] = []
    for source_key, package_count in (dict.fromkeys(records, 0) | dict(packages)).items():
        path, source_type = source_key
        lines += [
            "",
            f"{path} ({source_type})",
            f"  {counted(package_count, 'package')}; {counted(records[source_key], 'advisory record')}",
        ]
        lines += _package_sections(
            [finding for finding in report.findings if (finding.source_path, finding.source_type) == source_key],
            [finding for finding in shown if (finding.source_path, finding.source_type) == source_key],
        )
    return lines


def _package_sections(all_findings: list[DependencyFinding], shown: list[DependencyFinding]) -> list[str]:
    records = Counter((finding.ecosystem, finding.package, finding.version) for finding in all_findings)
    groups: dict[tuple[str, str, str], list[DependencyFinding]] = {identity: [] for identity in records}
    for finding in shown:
        groups[finding.ecosystem, finding.package, finding.version].append(finding)
    lines: list[str] = []
    for (ecosystem, package, version), findings in groups.items():
        lines += [
            f"  {ecosystem} {package}@{version}; {counted(records[ecosystem, package, version], 'advisory record')}",
            *(_finding_line(finding) for finding in findings),
        ]
    return lines
