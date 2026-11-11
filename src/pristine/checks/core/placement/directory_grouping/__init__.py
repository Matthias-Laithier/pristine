from pathlib import PurePosixPath

from pristine.checks.core.placement.directory_grouping.buckets import vague_buckets
from pristine.checks.core.placement.directory_grouping.file_count import crowded_directories
from pristine.checks.core.placement.directory_grouping.layout import (
    RULE_ID,
    code_files_by_directory,
    grouped_directories,
    holds_generated_code,
)
from pristine.checks.core.placement.directory_grouping.single_file import single_file_folders
from pristine.checks.definitions import PathCheck
from pristine.reports.findings import Finding


def check_directory_grouping(paths: list[str]) -> list[Finding]:
    directories = code_files_by_directory(paths)
    grouped = grouped_directories(directories)
    findings = [*crowded_directories(directories), *single_file_folders(grouped), *vague_buckets(grouped)]
    return [
        finding for finding in findings if not holds_generated_code(directories[PurePosixPath(finding.path).parent])
    ]


CHECK = PathCheck(
    rule_id=RULE_ID,
    title="Group Files by Cohesive Responsibility",
    summary=(
        "Directories holding more than 8 code files directly (error above 15), folders holding a single code "
        "file, and vague bucket directories (common/, misc/, helpers/, utils/, util/). Empty __init__.py files, "
        "File-based routes, migrations, generated, vendored, and test paths are exempt."
    ),
    run=check_directory_grouping,
)
