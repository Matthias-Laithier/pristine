from pristine.checks.registry import FileCheck, register_file_check
from pristine.reports.findings import Finding, Limit
from pristine.syntax.parsing import ParsedFile

RULE_ID = "CR-1"
FILE_LINE_LIMIT = Limit(target=150, hard=200)


def check_file_size(parsed: ParsedFile) -> list[Finding]:
    line_count = len(parsed.text.splitlines())
    severity = FILE_LINE_LIMIT.severity_for(line_count)
    if severity is None:
        return []
    message = f"file has {line_count} lines ({FILE_LINE_LIMIT.describe()}); split it along clean boundaries"
    return [Finding(parsed.path, 1, RULE_ID, severity, message)]


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=f"Code file length in lines, all lines counted ({FILE_LINE_LIMIT.describe()}).",
        run=check_file_size,
    )
)
