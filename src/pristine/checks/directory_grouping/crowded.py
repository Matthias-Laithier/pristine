from pathlib import PurePosixPath

from pristine.checks.directory_grouping.layout import directory_finding
from pristine.checks.directory_grouping.name_groups import prefix_groups
from pristine.reports.findings import Finding

MIN_CODE_FILES = 12
MIN_GROUP_SIZE = 3
MIN_GROUPS = 2
MIN_GROUPED_SHARE = 0.45
FLAT_PACKAGE_SUFFIXES = frozenset({".go"})
PRESCRIBED_FOLDER_NAMES = frozenset({"services", "commands"})


def crowded_finding(files: list[PurePosixPath]) -> Finding | None:
    directory = files[0].parent
    if len(files) < MIN_CODE_FILES or directory.name.lower() in PRESCRIBED_FOLDER_NAMES:
        return None
    code = [path for path in files if path.suffix not in FLAT_PACKAGE_SUFFIXES]
    groups = prefix_groups(directory, code, MIN_GROUP_SIZE)
    if len(groups) < MIN_GROUPS or sum(groups.values()) < MIN_GROUPED_SHARE * len(files):
        return None
    named = ", ".join(f"{prefix}* ({count} files)" for prefix, count in groups.items())
    return directory_finding(
        files,
        f"directory holds {len(files)} code files that form several groups: {named}; "
        "move each group into a subdirectory named after its responsibility",
    )


def crowded_directories(directories: dict[PurePosixPath, list[PurePosixPath]]) -> list[Finding]:
    return [finding for files in directories.values() if (finding := crowded_finding(files)) is not None]
