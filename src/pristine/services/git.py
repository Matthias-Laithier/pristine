import os
import shutil
import subprocess
from pathlib import Path

GIT_TIMEOUT_SECONDS = 30


def ls_files(directory: Path, *options: str) -> list[str] | None:
    git = shutil.which("git")
    if git is None:
        return None
    try:
        result = subprocess.run(
            [git, "-C", str(directory), "ls-files", *options, "-z"],
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return [name for name in os.fsdecode(result.stdout).split("\0") if name]


def listed_files(directory: Path) -> list[Path] | None:
    names = ls_files(directory, "--cached", "--others", "--exclude-standard")
    return None if names is None else [directory / name for name in names if (directory / name).is_file()]


def tracked_files(directory: Path) -> frozenset[str] | None:
    names = ls_files(directory, "--cached")
    return None if names is None else frozenset(names)
