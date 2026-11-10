import os
import shutil
import subprocess
from pathlib import Path

GIT_TIMEOUT_SECONDS = 30
GIT_ENTRY = ".git"
DEFAULT_BRANCH_HEAD = "refs/remotes/origin/HEAD"
DEFAULT_BRANCH_FALLBACKS = ("refs/remotes/origin/main", "refs/remotes/origin/master")
UNCHANGED_LINE_COUNTS = ("0", "0")
BINARY_COUNT = "-"
EDITED_DIFF_OPTIONS = (
    "--numstat",
    "-z",
    "--no-renames",
    "--no-textconv",
    "--ignore-all-space",
    "--ignore-blank-lines",
    "--diff-filter=M",
)


def git_output(directory: Path, *arguments: str) -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    try:
        result = subprocess.run(
            [git, "-C", str(directory), *arguments],
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if result.returncode != 0:
        return None
    return os.fsdecode(result.stdout)


def ls_files(directory: Path, *options: str) -> list[str] | None:
    output = git_output(directory, "ls-files", *options, "-z")
    return None if output is None else [name for name in output.split("\0") if name]


def listed_files(directory: Path) -> list[Path] | None:
    names = ls_files(directory, "--cached", "--others", "--exclude-standard")
    return None if names is None else [directory / name for name in names if (directory / name).is_file()]


def tracked_files(directory: Path) -> frozenset[str] | None:
    names = ls_files(directory, "--cached")
    return None if names is None else frozenset(names)


def repository_root(directory: Path) -> Path | None:
    return next((folder for folder in (directory, *directory.parents) if (folder / GIT_ENTRY).exists()), None)


def ref_exists(root: Path, ref: str) -> bool:
    return git_output(root, "rev-parse", "--verify", "--quiet", ref) is not None


def default_branch(root: Path) -> str | None:
    head = git_output(root, "symbolic-ref", "--quiet", DEFAULT_BRANCH_HEAD)
    if head is not None:
        return head.strip()
    return next((ref for ref in DEFAULT_BRANCH_FALLBACKS if ref_exists(root, ref)), None)


def content_edited(entry: str) -> bool:
    added, deleted, _ = entry.split("\t", 2)
    return (added, deleted) != UNCHANGED_LINE_COUNTS


def is_complete_history(root: Path) -> bool:
    output = git_output(root, "rev-parse", "--is-shallow-repository")
    return output is not None and output.strip() == "false"


def edited_since_default_branch(root: Path) -> frozenset[str] | None:
    branch = default_branch(root) if is_complete_history(root) else None
    base = None if branch is None else git_output(root, "merge-base", "HEAD", branch)
    if base is None:
        return None
    output = git_output(root, "diff", *EDITED_DIFF_OPTIONS, base.strip(), "--")
    if output is None:
        return None
    entries = [entry for entry in output.split("\0") if entry]
    return frozenset(entry.split("\t", 2)[2] for entry in entries if content_edited(entry))


def line_changes(root: Path, base: str) -> list[tuple[str, int, int]] | None:
    output = git_output(root, "diff", "--numstat", "-z", "--no-renames", base, "--")
    if output is None:
        return None
    entries = [entry.split("\t", 2) for entry in output.split("\0") if entry]
    return [(path, int(added), int(deleted)) for added, deleted, path in entries if added != BINARY_COUNT]


def untracked_files(root: Path) -> list[str] | None:
    return ls_files(root, "--others", "--exclude-standard")


def changed_names(root: Path, base: str, status: str) -> list[str]:
    output = git_output(root, "diff", "--name-only", "-z", "--no-renames", f"--diff-filter={status}", base, "--")
    return [] if output is None else [name for name in output.split("\0") if name]
