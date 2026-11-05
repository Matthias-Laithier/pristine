from pristine.findings import Finding, Severity
from pristine.project.loading import MAKEFILE_NAMES, Project
from pristine.project.makefile import COMPLETE_GATE, FAST_GATE
from pristine.project.tools import Ecosystem

RULE_ID = "TL-1"
ROOT = "."
FIRST_LINE = 1
CONTRACT_TARGETS = ("dev", FAST_GATE, COMPLETE_GATE)
BUILD_TARGET = "build"
BUILD_SCRIPT = "build"


def missing_makefile(project: Project) -> list[Finding]:
    if project.makefile_path is not None:
        return []
    message = "no Makefile at the repository root; add one with the dev, check, and check-all targets"
    return [Finding(project.shown(ROOT), FIRST_LINE, RULE_ID, Severity.ERROR, message)]


def missing_contract_targets(project: Project) -> list[Finding]:
    if project.makefile is None:
        return []
    path = project.shown(project.makefile.path)
    return [
        Finding(path, FIRST_LINE, RULE_ID, Severity.ERROR, f"the Makefile has no '{target}' target")
        for target in CONTRACT_TARGETS
        if target not in project.makefile.rules
    ]


def artifact_evidence(project: Project) -> str | None:
    container_files = project.container_build_files()
    if container_files:
        return f"container build file {container_files[0]}"
    manifest = project.root_manifest(Ecosystem.JAVASCRIPT)
    if manifest and BUILD_SCRIPT in manifest.scripts:
        return f"'{BUILD_SCRIPT}' script in {manifest.path}"
    return None


def missing_build_target(project: Project) -> list[Finding]:
    if project.makefile is None or BUILD_TARGET in project.makefile.rules:
        return []
    evidence = artifact_evidence(project)
    if evidence is None:
        return []
    message = f"the project produces artifacts ({evidence}) but the Makefile has no '{BUILD_TARGET}' target"
    return [Finding(project.shown(project.makefile.path), FIRST_LINE, RULE_ID, Severity.WARNING, message)]


def component_makefiles(project: Project) -> list[Finding]:
    nested = [path for path in project.files_named(MAKEFILE_NAMES) if "/" in path]
    if not nested:
        return []
    message = f"component Makefiles found ({', '.join(nested)}); keep one Makefile at the repository root"
    return [Finding(project.shown(project.makefile_path or ROOT), FIRST_LINE, RULE_ID, Severity.WARNING, message)]


CHECKS = (missing_makefile, missing_contract_targets, missing_build_target, component_makefiles)
