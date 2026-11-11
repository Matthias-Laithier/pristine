from dataclasses import replace

from pristine.checks.composition.stateless_classes import python, scripts
from pristine.reports.findings import Finding
from pristine.syntax.parsing import ParsedFile


def check_stateless_classes(parsed: ParsedFile) -> list[Finding]:
    return python.check_stateless_classes(parsed) + scripts.check_stateless_classes(parsed)


CHECK = replace(
    python.CHECK,
    summary=python.CHECK.summary
    + " JS/TS: plain classes with one public static operation and optional private helpers, "
    "no state, this/super use, inheritance, decorators, or non-namespace references in their module.",
    run=check_stateless_classes,
)
