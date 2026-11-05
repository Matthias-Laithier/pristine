from pristine.checks.registry import FileCheck, register_file_check
from pristine.checks.unbounded_calls.go_calls import scan_go
from pristine.checks.unbounded_calls.python_calls import scan_python
from pristine.checks.unbounded_calls.script_calls import scan_script
from pristine.findings import Finding
from pristine.parsing import ParsedFile, line_of
from pristine.services.grammars import SCRIPT_LANGUAGES

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


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Known external calls without a timeout: Python requests, subprocess, urlopen, socket, and smtplib; "
            "server-side JS/TS fetch without signal and axios without timeout; Go http.Get and http.Client."
        ),
        run=check_unbounded_calls,
    )
)
