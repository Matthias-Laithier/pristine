from collections.abc import Callable, Iterator

from pristine.checks.boundaries.data_flow.injection.constructed import Injection
from pristine.checks.boundaries.data_flow.injection.python.execution import scan_execution
from pristine.checks.boundaries.data_flow.injection.python.sql import scan_sql
from pristine.checks.boundaries.data_flow.injection.scripts.injection import scan_script
from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding, Severity
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.calls import calls_of
from pristine.syntax.parsing import ParsedFile, line_of

CHECK_ID = "SAFE-6"


def scan_python(parsed: ParsedFile) -> Iterator[Injection]:
    calls = list(calls_of(parsed, "call"))
    yield from scan_sql(calls)
    yield from scan_execution(parsed, calls)


SCANNERS: dict[str, Callable[[ParsedFile], Iterator[Injection]]] = dict.fromkeys(SCRIPT_LANGUAGES, scan_script) | {
    "python": scan_python,
}


def check_injection(parsed: ParsedFile) -> list[Finding]:
    scanner = SCANNERS.get(parsed.language)
    injections = [] if scanner is None else scanner(parsed)
    return [
        Finding(parsed.path, line_of(injection.node), CHECK_ID, Severity.ERROR, injection.message)
        for injection in injections
    ]


CHECK = FileCheck(
    check_id=CHECK_ID,
    title="Injection Patterns",
    summary=(
        "Injection-prone construction: Python SQL built by formatting or concatenation, shell commands, eval, "
        "pickle, and unsafe yaml.load; JS/TS/JSX/TSX non-literal markup, child_process exec of built strings, "
        "Prisma raw unsafe queries, and eval."
    ),
    run=check_injection,
)
