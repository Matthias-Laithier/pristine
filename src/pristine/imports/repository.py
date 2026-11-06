from functools import cache
from pathlib import Path, PurePath

from pristine.files.discovery import cwd_relative
from pristine.files.path_roles import is_cache, is_vendored
from pristine.services.git import listed_files

GIT_ENTRY = ".git"


@cache
def repository_root(directory: Path) -> Path | None:
    if (directory / GIT_ENTRY).exists():
        return directory
    return None if directory.parent == directory else repository_root(directory.parent)


@cache
def repository_files(root: Path) -> tuple[str, ...]:
    listed_prefix, resolved_root = f"{root.as_posix()}/", root.resolve().as_posix()
    names = (file.as_posix().removeprefix(listed_prefix) for file in listed_files(root) or [])
    kept = (name for name in names if not is_vendored(PurePath(name)) and not is_cache(PurePath(name)))
    return tuple(cwd_relative(f"{resolved_root}/{name}") for name in kept)


def with_repository_files(paths: list[str]) -> list[str]:
    roots = {repository_root(Path(path).absolute().parent) for path in paths}
    expanded = [file for root in roots if root is not None for file in repository_files(root)]
    return sorted({*paths, *expanded})
