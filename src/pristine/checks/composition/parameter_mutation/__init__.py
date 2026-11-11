from dataclasses import replace

from pristine.checks.composition.parameter_mutation import python, scripts
from pristine.reports.findings import Finding
from pristine.syntax.parsing import ParsedFile


def check_parameter_mutation(parsed: ParsedFile) -> list[Finding]:
    return python.check_parameter_mutation(parsed) + scripts.check_parameter_mutation(parsed)


CHECK = replace(
    python.CHECK,
    summary=python.CHECK.summary + " TS: public module-level functions and assigned arrows writing typed array, Map, "
    "Record, or inline object parameters, or calling known array/Map mutators, with no rebinding or callback use.",
    run=check_parameter_mutation,
)
