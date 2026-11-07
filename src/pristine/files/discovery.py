import os
from pathlib import Path, PurePath

from pristine.files.path_roles import is_cache, is_vendored
from pristine.services.git import ls_files


def _listed_repository_files(directory: Path) -> list[Path] | None:
    names = ls_files(directory, "--cached", "--others", "--exclude-standard")
    if names is None:
        return None
    files = (
        file
        for name in names
        if not is_vendored(PurePath(name))
        and not is_cache(PurePath(name))
        and (file := directory / name).is_file()
    )
    return list(files)


def walked_files(directory: Path) -> list[Path]:
    return [
        path
        for path in directory.rglob("*")
        if path.is_file()
        and not is_vendored(relative := path.relative_to(directory))
        and not is_cache(relative)
        and not any(part.startswith(".") for part in relative.parts)
    ]


def expand(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    listed = _listed_repository_files(path)
    return walked_files(path) if listed is None else listed


def cwd_relative(resolved: str) -> str:
    current = os.getcwd()
    return "." if resolved == current else resolved.removeprefix(current.rstrip("/") + "/")


def display_path(path: Path) -> str:
    return cwd_relative(path.resolve().as_posix())


def is_excluded(shown_path: str, patterns: list[str]) -> bool:
    candidate = PurePath(shown_path)
    return any(candidate.full_match(pattern) or candidate.full_match(f"{pattern}/**") for pattern in patterns)


def missing_paths(paths: list[Path]) -> tuple[str, ...]:
    return tuple(display_path(path) for path in paths if not path.is_file() and not path.is_dir())


def discover_files(paths: list[Path], excludes: list[str]) -> list[str]:
    shown = {display_path(file) for path in paths for file in expand(path)}
    return sorted(path for path in shown if not is_excluded(path, excludes))
