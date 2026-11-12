import os
from functools import cache
from pathlib import Path, PurePath

from pristine.files.discovery import relative_to
from pristine.files.path_roles import is_cache, is_vendored
from pristine.services.git import UNIGNORED_FILES, ls_files

GIT_ENTRY = ".git"


@cache
def repository_root(directory: Path) -> Path | None:
    if (directory / GIT_ENTRY).exists():
        return directory
    return None if directory.parent == directory else repository_root(directory.parent)


def is_kept(name: str) -> bool:
    return not is_vendored(PurePath(name)) and not is_cache(PurePath(name))


@cache
def repository_files(root: Path, current: str) -> tuple[str, ...]:
    listed, resolved_root = root.as_posix(), root.resolve().as_posix()
    names = (name for name in ls_files(root, *UNIGNORED_FILES) or [] if os.path.isfile(f"{listed}/{name}"))
    return tuple(relative_to(f"{resolved_root}/{name}", current) for name in names if is_kept(name))


def with_repository_files(paths: list[str]) -> list[str]:
    current = os.getcwd()
    directories = {os.path.dirname(os.path.join(current, path)) for path in paths}
    roots = {repository_root(Path(directory)) for directory in directories}
    expanded = [file for root in roots if root is not None for file in repository_files(root, current)]
    return sorted({*paths, *expanded})
