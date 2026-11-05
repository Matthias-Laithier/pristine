from pathlib import Path

from pristine.outcomes import Checked, Outcome, Unchecked
from pristine.project import automation, gates, layout, lockfiles
from pristine.project.loading import load_project
from pristine.report import Report, build_report

PROJECT_RULE_SUMMARIES = {
    "TL-1": "A root Makefile with dev, check, and check-all, a build target when the project ships artifacts, and no component Makefiles.",
    "TL-2": "check-all runs check.",
    "TL-3": "A formatter, a linter, and a type checker are configured and run by make check, the formatter in check mode.",
    "TL-4": "A deployable project commits its lockfile.",
}

PROJECT_CHECKS = (*layout.CHECKS, *gates.CHECKS, *automation.CHECKS, *lockfiles.CHECKS)


def inspect_project(directory: Path) -> Report:
    project = load_project(directory)
    findings = [finding for check in PROJECT_CHECKS for finding in check(project)]
    reader = project.reader
    checked: dict[str, Outcome] = {project.shown(path): Checked([]) for path in reader.checked}
    unchecked = {project.shown(path): Unchecked(reason) for path, reason in reader.unchecked.items()}
    return build_report(checked | unchecked, findings)
