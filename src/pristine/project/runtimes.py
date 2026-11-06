from dataclasses import dataclass

from pristine.project.repository.loading import Project
from pristine.project.repository.tools import Ecosystem
from pristine.reports.findings import Finding, Severity

RULE_ID = "TL-4"
FIRST_LINE = 1


@dataclass(frozen=True)
class RuntimePin:
    ecosystem: Ecosystem
    runtime: str
    version_files: tuple[str, ...]
    manifest_field: str


RUNTIME_PINS = (
    RuntimePin(Ecosystem.PYTHON, "Python", (".python-version",), "requires-python"),
    RuntimePin(Ecosystem.JAVASCRIPT, "Node.js", (".nvmrc", ".node-version"), "engines.node"),
)


def unpinned(project: Project, pin: RuntimePin) -> list[Finding]:
    manifest = project.root_manifest(pin.ecosystem)
    if manifest is None or manifest.pins_runtime or project.entries.intersection(pin.version_files):
        return []
    message = (
        f"the {pin.runtime} version is not pinned; set {pin.manifest_field} in {manifest.path} "
        f"or add one of {', '.join(pin.version_files)}"
    )
    return [Finding(project.shown(manifest.path), FIRST_LINE, RULE_ID, Severity.WARNING, message)]


def unpinned_runtimes(project: Project) -> list[Finding]:
    return [finding for pin in RUNTIME_PINS for finding in unpinned(project, pin)]


CHECKS = (unpinned_runtimes,)
