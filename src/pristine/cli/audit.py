import json
from dataclasses import asdict

from pristine.audit.models import AuditReport, DependencyFinding
from pristine.cli.rendering import NEXT_STEP

__all__ = ["render_json", "render_text"]

SCOPE = (
    "Native-extracted PyPI package/version known-advisory matches only; no installed-dependency, package-origin, "
    "full-project, or exploitability assurance. Fixed versions are contextual advisory releases, not upgrade recommendations."
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
    lines = ["Dependency audit", SCOPE]
    lines.extend(
        f"source: {source.path} ({source.source_type}), {source.package_count} packages" for source in report.sources
    )
    lines.extend(_finding_line(finding) for finding in shown)
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
    if finding.fixed_versions:
        details.append(
            "advisory-reported fixed releases (not upgrade recommendations): " + ", ".join(finding.fixed_versions)
        )
    else:
        details.append("fixed versions: not reported")
    return f"{finding.source_path}: {finding.ecosystem} {finding.package}@{finding.version}: " + "; ".join(details)
