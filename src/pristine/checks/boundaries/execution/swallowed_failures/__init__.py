from collections.abc import Callable, Iterator

from pristine.checks.boundaries.execution.swallowed_failures.go import go_swallows
from pristine.checks.boundaries.execution.swallowed_failures.handlers import RULE_ID
from pristine.checks.boundaries.execution.swallowed_failures.jvm import typed_catch_swallows
from pristine.checks.boundaries.execution.swallowed_failures.python import python_swallows
from pristine.checks.boundaries.execution.swallowed_failures.scripts import script_swallows
from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding
from pristine.syntax.parsing import ParsedFile

type Detector = Callable[[ParsedFile], Iterator[Finding]]

DETECTORS: dict[str, Detector] = {
    "javascript": script_swallows,
    "typescript": script_swallows,
    "tsx": script_swallows,
    "python": python_swallows,
    "go": go_swallows,
    "java": typed_catch_swallows,
    "csharp": typed_catch_swallows,
    "kotlin": typed_catch_swallows,
}


def check_swallowed_failures(parsed: ParsedFile) -> list[Finding]:
    detector = DETECTORS.get(parsed.language)
    return [] if detector is None else list(detector(parsed))


CHECK = FileCheck(
    rule_id=RULE_ID,
    summary=(
        "Handlers that hide a failure: silent Python excepts, empty or empty-returning catches, "
        "and Go error checks that drop the error or return a nil error."
    ),
    run=check_swallowed_failures,
)
