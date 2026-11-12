import os
from pathlib import Path, PurePath

from pristine.files.path_roles import CACHE_DIRECTORIES, VENDORED_DIRECTORIES, is_cache, is_vendored
from pristine.services.git import UNIGNORED_FILES, ls_files


def _listed_repository_files(directory: Path) -> list[Path] | None:
    names = ls_files(directory, *UNIGNORED_FILES)
    if names is None:
        return None
    files = (
        file
        for name in names
        if not is_vendored(PurePath(name)) and not is_cache(PurePath(name)) and (file := directory / name).is_file()
    )
    return list(files)


def walked_files(directory: Path) -> list[Path]:
    files: list[Path] = []
    for base, directories, names in directory.walk():
        directories[:] = [
            name
            for name in directories
            if not name.startswith(".") and name not in VENDORED_DIRECTORIES and name not in CACHE_DIRECTORIES
        ]
        files.extend(path for name in names if not name.startswith(".") and (path := base / name).is_file())
    return files


def expand(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    listed = _listed_repository_files(path)
    return walked_files(path) if listed is None else listed


def relative_to(resolved: str, current: str) -> str:
    return "." if resolved == current else resolved.removeprefix(current.rstrip("/") + "/")


def cwd_relative(resolved: str) -> str:
    return relative_to(resolved, os.getcwd())


def display_path(path: Path) -> str:
    return cwd_relative(path.resolve().as_posix())


def display_paths(files: list[Path]) -> list[str]:
    current = os.getcwd()
    resolved_directories: dict[str, str] = {}
    shown = []
    for file in files:
        absolute = os.path.join(current, file)
        directory, name = os.path.split(absolute)
        if directory not in resolved_directories:
            resolved_directories[directory] = os.path.realpath(directory)
        is_link = os.path.islink(absolute)
        resolved = os.path.realpath(absolute) if is_link else os.path.join(resolved_directories[directory], name)
        shown.append(relative_to(resolved, current))
    return shown


def is_excluded(shown_path: str, patterns: list[str]) -> bool:
    candidate = PurePath(shown_path)
    return any(candidate.full_match(pattern) or candidate.full_match(f"{pattern}/**") for pattern in patterns)


def missing_paths(paths: list[Path]) -> tuple[str, ...]:
    return tuple(display_path(path) for path in paths if not path.is_file() and not path.is_dir())


def discover_files(paths: list[Path], excludes: list[str]) -> list[str]:
    shown = set(display_paths([file for path in paths for file in expand(path)]))
    return sorted(path for path in shown if not is_excluded(path, excludes))
