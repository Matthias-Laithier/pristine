from pristine.checks.registry import FileCheck, register_file_check
from pristine.findings import Finding, Limit
from pristine.parsing import FunctionSpan, ParsedFile

RULE_ID = "CR-12"
FUNCTION_LINE_LIMIT = Limit(target=30, hard=50)


def non_blank_line_count(lines: list[str], function: FunctionSpan) -> int:
    body = lines[function.start_line - 1 : function.end_line]
    return sum(1 for line in body if line.strip())


def check_function_size(parsed: ParsedFile) -> list[Finding]:
    lines = parsed.text.splitlines()
    findings = []
    for function in parsed.functions:
        line_count = non_blank_line_count(lines, function)
        severity = FUNCTION_LINE_LIMIT.severity_for(line_count)
        if severity is None:
            continue
        message = (
            f"function '{function.name}' has {line_count} non-blank lines "
            f"({FUNCTION_LINE_LIMIT.describe()}); extract named helpers along real jobs"
        )
        findings.append(Finding(parsed.path, function.start_line, RULE_ID, severity, message))
    return findings


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=f"Function and method length, blank lines excluded ({FUNCTION_LINE_LIMIT.describe()}).",
        run=check_function_size,
    )
)
