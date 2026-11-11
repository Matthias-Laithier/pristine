from pathlib import Path

from pristine.project import automation, gates, installs, layout, lockfiles, runtimes, strict_mode
from pristine.project.repository.loading import load_project
from pristine.reports.outcomes import Checked, Outcome, Unchecked
from pristine.reports.report import Report, build_report

CHECK_GROUPS = (
    ("PROJ-1", "Makefile Contract", "Root Makefile targets and component Makefile locations.", layout.CHECKS),
    ("PROJ-2", "Verification Gates", "The complete gate includes the fast gate.", gates.CHECKS),
    (
        "PROJ-3",
        "Static Analysis",
        "Supported formatter, lint, type-checker configuration and gate commands.",
        (*automation.CHECKS, *strict_mode.CHECKS),
    ),
    (
        "PROJ-4",
        "Reproducible Dependencies",
        "Supported lockfiles, frozen installs and runtime declarations.",
        (*lockfiles.CHECKS, *installs.CHECKS, *runtimes.CHECKS),
    ),
)
PROJECT_CHECKS = tuple(check for _, _, _, checks in CHECK_GROUPS for check in checks)


def inspect_project(directory: Path) -> Report:
    project = load_project(directory)
    findings = [finding for check in PROJECT_CHECKS for finding in check(project)]
    reader = project.reader
    checked: dict[str, Outcome] = {project.shown(path): Checked([]) for path in reader.checked}
    unchecked = {project.shown(path): Unchecked(reason) for path, reason in reader.unchecked.items()}
    return build_report(checked | unchecked, findings)
