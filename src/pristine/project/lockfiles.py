from pristine.project.repository.loading import Project
from pristine.project.repository.tools import Ecosystem
from pristine.reports.findings import Finding, FindingKind, Severity
from pristine.services.git import tracked_files

RULE_ID = "TL-4"
FIRST_LINE = 1
LOCKFILES = {
    "pyproject.toml": ("uv.lock", "poetry.lock", "pdm.lock", "pylock.toml"),
    "package.json": (
        "package-lock.json",
        "npm-shrinkwrap.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "bun.lock",
        "bun.lockb",
    ),
    "Cargo.toml": ("Cargo.lock",),
    "go.mod": ("go.sum",),
}


def missing_lockfile(project: Project, manifest: str, container_file: str) -> Finding:
    message = (
        f"deployable application (container build file {container_file}) has no committed lockfile for {manifest}; "
        f"commit one of {', '.join(LOCKFILES[manifest])}"
    )
    return Finding(project.shown(manifest), FIRST_LINE, RULE_ID, Severity.WARNING, message)


def unverified_go_lockfile(project: Project) -> Finding:
    message = (
        "cannot verify that the lockfile for go.mod is needed: the replace directives are not supported by this parser"
    )
    return Finding(project.shown("go.mod"), FIRST_LINE, RULE_ID, Severity.WARNING, message, FindingKind.VERIFICATION)


def go_lockfile_needs_verification(project: Project) -> bool:
    go_manifest = project.root_manifest(Ecosystem.GO)
    return go_manifest is not None and go_manifest.needs_lockfile is None


def uncommitted_lockfiles(project: Project) -> list[Finding]:
    container_files = project.container_build_files()
    manifests = [manifest for manifest in LOCKFILES if manifest in project.entries]
    if not container_files or not manifests:
        return []
    findings: list[Finding] = []
    if "go.mod" in manifests and go_lockfile_needs_verification(project):
        findings.append(unverified_go_lockfile(project))
    if all(not needs_lockfile(project, manifest) for manifest in manifests):
        return findings
    tracked = tracked_files(project.root)
    if tracked is None:
        message = "cannot verify that the lockfile is committed: 'git ls-files' failed, so this is not a readable git repository"
        findings.append(
            Finding(
                project.shown(manifests[0]),
                FIRST_LINE,
                RULE_ID,
                Severity.WARNING,
                message,
                FindingKind.VERIFICATION,
            )
        )
        return findings
    findings.extend(
        missing_lockfile(project, manifest, container_files[0])
        for manifest in manifests
        if tracked.isdisjoint(LOCKFILES[manifest]) and needs_lockfile(project, manifest)
    )
    return findings


def needs_lockfile(project: Project, manifest: str) -> bool:
    if manifest != "go.mod":
        return True
    go_manifest = project.root_manifest(Ecosystem.GO)
    return go_manifest is not None and go_manifest.needs_lockfile is True


CHECKS = (uncommitted_lockfiles,)
