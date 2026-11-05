from pathlib import PurePosixPath

from pristine.checks.directory_grouping.buckets import vague_buckets
from pristine.checks.directory_grouping.crowded import crowded_directories
from pristine.checks.directory_grouping.layout import RULE_ID, code_files_by_directory, holds_generated_code
from pristine.checks.directory_grouping.single_file import single_file_folders
from pristine.checks.registry import PathCheck, register_path_check
from pristine.findings import Finding


def check_directory_grouping(paths: list[str]) -> list[Finding]:
    directories = code_files_by_directory(paths)
    findings = [*crowded_directories(directories), *single_file_folders(directories), *vague_buckets(directories)]
    return [
        finding for finding in findings if not holds_generated_code(directories[PurePosixPath(finding.path).parent])
    ]


register_path_check(
    PathCheck(
        rule_id=RULE_ID,
        summary=(
            "Crowded flat directories of 12+ code files that form several name-prefix groups, folders holding a "
            "single code file, and vague bucket directories (common/, misc/, helpers/, utils/, util/). Package "
            "markers, framework routes, package-per-directory languages, migrations, templates, generated, "
            "vendored, and test paths are exempt."
        ),
        run=check_directory_grouping,
    )
)
