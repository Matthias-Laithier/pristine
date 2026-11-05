import posixpath
from functools import cache
from pathlib import Path, PurePath

from pristine.discovery import display_path
from pristine.path_roles import is_cache, is_vendored
from pristine.services.git import listed_files

GIT_ENTRY = ".git"


@cache
def repository_root(directory: Path) -> Path | None:
    if (directory / GIT_ENTRY).exists():
        return directory
    return None if directory.parent == directory else repository_root(directory.parent)


def repository_files(root: Path) -> list[str]:
    shown_root = display_path(root)
    names = (PurePath(file.as_posix()[len(root.as_posix()) + 1 :]) for file in listed_files(root) or [])
    kept = (name for name in names if not is_vendored(name) and not is_cache(name))
    return [posixpath.normpath(posixpath.join(shown_root, name.as_posix())) for name in kept]


def with_repository_files(paths: list[str]) -> list[str]:
    roots = {repository_root(Path(path).absolute().parent) for path in paths}
    expanded = [file for root in roots if root is not None for file in repository_files(root)]
    return sorted({*paths, *expanded})
