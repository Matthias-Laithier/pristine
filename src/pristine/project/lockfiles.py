from pristine.findings import Finding, Severity
from pristine.project.loading import Project
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


def uncommitted_lockfiles(project: Project) -> list[Finding]:
    container_files = project.container_build_files()
    manifests = [manifest for manifest in LOCKFILES if manifest in project.entries]
    if not container_files or not manifests:
        return []
    tracked = tracked_files(project.root)
    if tracked is None:
        message = "cannot verify that the lockfile is committed: 'git ls-files' failed, so this is not a readable git repository"
        return [Finding(project.shown(manifests[0]), FIRST_LINE, RULE_ID, Severity.WARNING, message)]
    return [
        missing_lockfile(project, manifest, container_files[0])
        for manifest in manifests
        if tracked.isdisjoint(LOCKFILES[manifest])
    ]


CHECKS = (uncommitted_lockfiles,)
