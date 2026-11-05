from pathlib import Path, PurePath

from pristine.path_roles import is_cache, is_vendored
from pristine.services.git import listed_files


class PathNotFound(Exception):
    pass


def walked_files(directory: Path) -> list[Path]:
    files = (path for path in directory.rglob("*") if path.is_file())
    return [path for path in files if not any(part.startswith(".") for part in path.relative_to(directory).parts)]


def expand(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise PathNotFound(str(path))
    listed = listed_files(path)
    files = walked_files(path) if listed is None else listed
    relative = ((file, file.relative_to(path)) for file in files)
    return [file for file, inside in relative if not is_vendored(inside) and not is_cache(inside)]


def display_path(path: Path) -> str:
    absolute = path.resolve()
    try:
        return absolute.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return absolute.as_posix()


def is_excluded(shown_path: str, patterns: list[str]) -> bool:
    candidate = PurePath(shown_path)
    return any(candidate.full_match(pattern) or candidate.full_match(f"{pattern}/**") for pattern in patterns)


def discover_files(paths: list[Path], excludes: list[str]) -> list[str]:
    shown = {display_path(file) for path in paths for file in expand(path)}
    return sorted(path for path in shown if not is_excluded(path, excludes))
