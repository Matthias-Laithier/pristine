from dataclasses import replace

from pristine.checks.composition.concrete_inheritance import python, scripts
from pristine.reports.findings import Finding
from pristine.syntax.parsing import ParsedFile


def check_concrete_inheritance(parsed: ParsedFile) -> list[Finding]:
    return python.check_concrete_inheritance(parsed) + scripts.check_concrete_inheritance(parsed)


CHECK = replace(
    python.CHECK,
    summary=python.CHECK.summary + " JS/TS: the same single-variant override heuristic for plain same-module classes.",
    run=check_concrete_inheritance,
)
