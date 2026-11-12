import os
import re
from collections import Counter
from pathlib import PurePosixPath

from pristine.checks.core.placement.directory_grouping.layout import directory_finding, is_code
from pristine.files.path_roles import RESULT_CACHE_DIRECTORY
from pristine.reports.findings import Finding

WORD_BOUNDARY = re.compile(r"[_.\-\s()\[\]]+|(?<=[a-z0-9])(?=[A-Z])")
PACKAGE_MARKERS = frozenset({"__init__.py", "__main__.py"})
INDEX_STEM = "index"
ROUTING_FOLDER_NAMES = frozenset({"app", "pages", "routes", "functions", "api"})
ROUTING_SUFFIXES = frozenset({".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"})
PRESCRIBED_FOLDER_NAMES = frozenset({"services", "scripts", "bin", "cmd", "static", "public"})
IGNORED_ENTRIES = frozenset({"__pycache__", RESULT_CACHE_DIRECTORY})
CURRENT_DIRECTORY = PurePosixPath(".")
TEST_SUPPORT_WORD = "test"

type Directories = dict[PurePosixPath, list[PurePosixPath]]


def words(name: str) -> list[str]:
    return [word.lower() for word in WORD_BOUNDARY.split(name) if word]


def is_package_marker(path: PurePosixPath) -> bool:
    return path.name in PACKAGE_MARKERS or path.stem == INDEX_STEM


def is_named_slot(path: PurePosixPath) -> bool:
    folder_words = words(path.parent.name)
    return words(path.name)[: len(folder_words)] == folder_words or TEST_SUPPORT_WORD in folder_words


def is_framework_placed(path: PurePosixPath) -> bool:
    folders = {name.lower() for name in path.parts[:-1]}
    is_routed = path.suffix in ROUTING_SUFFIXES and not ROUTING_FOLDER_NAMES.isdisjoint(folders)
    is_prescribed = not PRESCRIBED_FOLDER_NAMES.isdisjoint(folders)
    return is_routed or is_prescribed


def entries_of(directory: PurePosixPath) -> list[PurePosixPath]:
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    return [directory / name for name in names if name not in IGNORED_ENTRIES]


def holds_only(path: PurePosixPath) -> bool:
    return entries_of(path.parent) == [path]


def sits_in_folder_layout(path: PurePosixPath) -> bool:
    siblings = entries_of(path.parent.parent)
    folders = sum(os.path.isdir(sibling) for sibling in siblings)
    return folders > sum(os.path.isfile(sibling) and is_code(sibling) for sibling in siblings)


def repeated_layouts(directories: Directories) -> set[str]:
    folder_names = {directory.name.lower() for directory, files in directories.items() if len(files) > 1}
    slots = Counter((directory.parent, path.name) for directory, files in directories.items() for path in files)
    return folder_names | {f"{parent}/{name}" for (parent, name), count in slots.items() if count > 1}


def follows_repeated_layout(path: PurePosixPath, layouts: set[str]) -> bool:
    return path.parent.name.lower() in layouts or f"{path.parent.parent}/{path.name}" in layouts


def is_lone_file(files: list[PurePosixPath], layouts: set[str]) -> bool:
    path = files[0]
    if len(files) > 1 or path.parent == CURRENT_DIRECTORY or follows_repeated_layout(path, layouts):
        return False
    is_conventional = is_package_marker(path) or is_named_slot(path) or is_framework_placed(path)
    return not is_conventional and holds_only(path) and not sits_in_folder_layout(path)


def single_file_folders(directories: Directories) -> list[Finding]:
    layouts = repeated_layouts(directories)
    return [
        directory_finding(
            files,
            f"folder '{directory.name}/' holds only this file; move the file into the parent directory, "
            "or into the folder of the files it belongs with",
        )
        for directory, files in directories.items()
        if is_lone_file(files, layouts)
    ]
