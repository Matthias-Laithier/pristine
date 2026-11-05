from collections.abc import Callable, Iterator

from pristine.checks.injection.constructed import Injection
from pristine.checks.injection.go_injection import scan_go
from pristine.checks.injection.python_execution import scan_execution
from pristine.checks.injection.python_sql import scan_sql
from pristine.checks.injection.script_injection import scan_script
from pristine.checks.registry import FileCheck, register_file_check
from pristine.findings import Finding, Severity
from pristine.parsing import ParsedFile, line_of
from pristine.services.grammars import SCRIPT_LANGUAGES

RULE_ID = "BS-10"


def scan_python(parsed: ParsedFile) -> Iterator[Injection]:
    yield from scan_sql(parsed.root)
    yield from scan_execution(parsed.root)


SCANNERS: dict[str, Callable[[ParsedFile], Iterator[Injection]]] = dict.fromkeys(SCRIPT_LANGUAGES, scan_script) | {
    "python": scan_python,
    "go": scan_go,
}


def check_injection(parsed: ParsedFile) -> list[Finding]:
    scanner = SCANNERS.get(parsed.language)
    injections = [] if scanner is None else scanner(parsed)
    return [
        Finding(parsed.path, line_of(injection.node), RULE_ID, Severity.ERROR, injection.message)
        for injection in injections
    ]


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Injection-prone construction: Python SQL built by formatting or concatenation, shell commands, eval, "
            "pickle, and unsafe yaml.load; JS/TS non-literal markup, child_process exec of built strings, "
            "Prisma raw unsafe queries, and eval; Go SQL built with Sprintf or concatenation, and sh -c."
        ),
        run=check_injection,
    )
)
