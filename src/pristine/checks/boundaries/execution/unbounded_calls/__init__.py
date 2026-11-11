from pristine.checks.boundaries.execution.unbounded_calls.go_calls import scan_go
from pristine.checks.boundaries.execution.unbounded_calls.python_calls import scan_python
from pristine.checks.boundaries.execution.unbounded_calls.script_calls import scan_script
from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.parsing import ParsedFile, line_of

RULE_ID = "BS-3"
SCANNERS = dict.fromkeys(SCRIPT_LANGUAGES, scan_script) | {"python": scan_python, "go": scan_go}


def check_unbounded_calls(parsed: ParsedFile) -> list[Finding]:
    scanner = SCANNERS.get(parsed.language)
    violations = [] if scanner is None else scanner(parsed)
    return [
        Finding(
            parsed.path,
            line_of(violation.node),
            RULE_ID,
            violation.call.severity,
            f"'{violation.callee}' runs without a timeout or deadline; {violation.call.fix}",
        )
        for violation in violations
    ]


CHECK = FileCheck(
    rule_id=RULE_ID,
    title="Bound Every External Call",
    summary=(
        "Known external calls without a timeout: Python requests, subprocess, urlopen, socket, and smtplib; "
        "server-side JS/TS fetch without signal and axios without timeout; Go http.Get and http.Client."
    ),
    run=check_unbounded_calls,
)
