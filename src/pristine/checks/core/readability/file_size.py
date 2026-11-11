from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding, Severity
from pristine.syntax.parsing import ParsedFile

CHECK_ID = "STR-1"
FILE_LINE_LIMIT = 200


def check_file_size(parsed: ParsedFile) -> list[Finding]:
    line_count = len(parsed.text.splitlines())
    if line_count <= FILE_LINE_LIMIT:
        return []
    message = f"file has {line_count} lines (hard limit {FILE_LINE_LIMIT}); split it along clean boundaries"
    return [Finding(parsed.path, 1, CHECK_ID, Severity.ERROR, message)]


CHECK = FileCheck(
    check_id=CHECK_ID,
    title="File Size",
    summary=f"Code file length in lines, all lines counted (hard limit {FILE_LINE_LIMIT}).",
    run=check_file_size,
)
