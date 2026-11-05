from collections import defaultdict
from pathlib import PurePosixPath

from pristine.checks.directory_grouping.layout import directory_finding
from pristine.findings import Finding

VAGUE_BUCKET_NAMES = frozenset({"common", "misc", "helpers", "utils", "util"})
PACKAGE_PATH_ROOTS = frozenset({"java", "kotlin"})


def bucket_of(path: PurePosixPath) -> PurePosixPath | None:
    folders = path.parts[:-1]
    if not PACKAGE_PATH_ROOTS.isdisjoint(folders):
        return None
    position = next((index for index, name in enumerate(folders) if name.lower() in VAGUE_BUCKET_NAMES), None)
    return None if position is None else PurePosixPath(*folders[: position + 1])


def vague_buckets(directories: dict[PurePosixPath, list[PurePosixPath]]) -> list[Finding]:
    buckets: dict[PurePosixPath, list[PurePosixPath]] = defaultdict(list)
    located = ((bucket_of(path), path) for files in directories.values() for path in files)
    for bucket, path in located:
        if bucket is not None:
            buckets[bucket].append(path)
    return [
        directory_finding(
            files,
            f"vague bucket directory '{bucket.name}/'; name the directory after the responsibility its files share, "
            "or move each file beside the code that uses it",
        )
        for bucket, files in buckets.items()
    ]
