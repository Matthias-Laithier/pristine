from collections.abc import Callable, Iterator

from pristine.checks.boundaries.execution.swallowed_failures.handlers import RULE_ID
from pristine.checks.boundaries.execution.swallowed_failures.python import python_swallows
from pristine.checks.boundaries.execution.swallowed_failures.scripts import script_swallows
from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.parsing import ParsedFile

type Detector = Callable[[ParsedFile], Iterator[Finding]]

DETECTORS: dict[str, Detector] = dict.fromkeys(SCRIPT_LANGUAGES, script_swallows) | {
    "python": python_swallows,
}


def check_swallowed_failures(parsed: ParsedFile) -> list[Finding]:
    detector = DETECTORS.get(parsed.language)
    return [] if detector is None else list(detector(parsed))


CHECK = FileCheck(
    rule_id=RULE_ID,
    title="Do Not Swallow Failures",
    summary=("Handlers that hide a failure: silent Python excepts and empty or empty-returning JS/TS/JSX/TSX catches."),
    run=check_swallowed_failures,
)
