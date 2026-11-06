from pathlib import Path

from pristine.project import automation, gates, installs, layout, lockfiles, runtimes, strict_mode
from pristine.project.repository.loading import load_project
from pristine.reports.outcomes import Checked, Outcome, Unchecked
from pristine.reports.report import Report, build_report

PROJECT_CHECKS = (
    *layout.CHECKS,
    *gates.CHECKS,
    *automation.CHECKS,
    *strict_mode.CHECKS,
    *lockfiles.CHECKS,
    *installs.CHECKS,
    *runtimes.CHECKS,
)


def inspect_project(directory: Path) -> Report:
    project = load_project(directory)
    findings = [finding for check in PROJECT_CHECKS for finding in check(project)]
    reader = project.reader
    checked: dict[str, Outcome] = {project.shown(path): Checked([]) for path in reader.checked}
    unchecked = {project.shown(path): Unchecked(reason) for path, reason in reader.unchecked.items()}
    return build_report(checked | unchecked, findings)
