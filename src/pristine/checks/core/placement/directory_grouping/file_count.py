from pathlib import Path, PurePosixPath

from pristine.checks.core.placement.directory_grouping.layout import directory_finding
from pristine.reports.findings import Finding, Severity

TARGET_FILES = 8
HARD_LIMIT_FILES = 15
PACKAGE_MARKER = "__init__.py"
ROUTING_FOLDER_NAMES = frozenset({"pages", "routes"})
ROUTING_SUFFIXES = frozenset({".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"})


def is_empty_marker(path: PurePosixPath) -> bool:
    if path.name != PACKAGE_MARKER:
        return False
    try:
        return not Path(path).read_text(errors="replace").strip()
    except OSError:
        return False


def is_routed(path: PurePosixPath) -> bool:
    return path.suffix.lower() in ROUTING_SUFFIXES and path.parent.name.lower() in ROUTING_FOLDER_NAMES


def is_counted(path: PurePosixPath) -> bool:
    return not (is_routed(path) or is_empty_marker(path))


def count_finding(files: list[PurePosixPath]) -> Finding | None:
    counted = [path for path in files if is_counted(path)]
    if len(counted) <= TARGET_FILES:
        return None
    severity = Severity.ERROR if len(counted) > HARD_LIMIT_FILES else Severity.WARNING
    return directory_finding(
        counted,
        f"directory holds {len(counted)} code files, over the target of {TARGET_FILES} "
        f"(hard limit {HARD_LIMIT_FILES}); move each set of files that share a responsibility into a "
        "subdirectory named after it",
        severity,
    )


def crowded_directories(directories: dict[PurePosixPath, list[PurePosixPath]]) -> list[Finding]:
    return [finding for files in directories.values() if (finding := count_finding(files)) is not None]
