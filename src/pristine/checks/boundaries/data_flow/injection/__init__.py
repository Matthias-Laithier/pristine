import re
from collections.abc import Callable, Iterator

from pristine.checks.boundaries.data_flow.injection.constructed import SQL_START, Injection
from pristine.checks.boundaries.data_flow.injection.python.execution import scan_execution
from pristine.checks.boundaries.data_flow.injection.python.sql import scan_sql
from pristine.checks.boundaries.data_flow.injection.scripts.injection import scan_script
from pristine.checks.definitions import FileCheck
from pristine.checks.prefilters import mentions_any, requiring
from pristine.reports.findings import Finding, Severity
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.calls import calls_of
from pristine.syntax.parsing import ParsedFile, line_of

CHECK_ID = "SAFE-6"
QUOTED_SQL = re.compile(r"[\"']" + SQL_START.pattern, re.IGNORECASE)
MENTIONS_INJECTION = mentions_any(
    {
        "python": ("eval", "exec", "system", "popen", "output", "shell", "pickle", "yaml"),
        **dict.fromkeys(
            SCRIPT_LANGUAGES, ("child_process", "innerHTML", "outerHTML", "InnerHTML", "RawUnsafe", "eval", "Function")
        ),
    }
)


def scan_python(parsed: ParsedFile) -> Iterator[Injection]:
    calls = list(calls_of(parsed, "call"))
    yield from scan_sql(calls)
    yield from scan_execution(parsed, calls)


SCANNERS: dict[str, Callable[[ParsedFile], Iterator[Injection]]] = dict.fromkeys(SCRIPT_LANGUAGES, scan_script) | {
    "python": scan_python,
}


def may_inject(parsed: ParsedFile) -> bool:
    quoted_sql = parsed.language == "python" and QUOTED_SQL.search(parsed.text) is not None
    return quoted_sql or MENTIONS_INJECTION(parsed)


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
    run=requiring(may_inject, check_injection),
)
