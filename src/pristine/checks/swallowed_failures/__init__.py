import re
from collections.abc import Callable, Iterator
from functools import cache

from tree_sitter import Node

from pristine.checks.registry import FileCheck, register_file_check
from pristine.findings import Finding, Severity
from pristine.package_modules import import_package_modules
from pristine.parsing import ParsedFile, line_of, node_text
from pristine.registration import registering
from pristine.syntax_kinds import COMMENT_KINDS

RULE_ID = "BS-4"
DETECTORS_PACKAGE = "pristine.checks.swallowed_failures"
PROPAGATE_HINT = "handle it, translate it while keeping the cause, or let it propagate"
NARROW_HINT = "narrow the catch to the expected error, or let the failure propagate"
LOGGING_FUNCTION = re.compile(r"([\w$.]*\.)?(\w*logger|logging|log|console)\.\w+|print", re.IGNORECASE)
DEFAULT_NAME = re.compile(r"([\w$]+\.)*\w*default\w*", re.IGNORECASE)
CALL_KINDS = frozenset({"call", "call_expression"})
RETURN_KEYWORD = "return "
EXPRESSION_STATEMENT = "expression_statement"
EXPECTED_EXCEPTIONS = frozenset(
    {"FileNotFoundError", "FileExistsError", "ProcessLookupError", "StopIteration", "StopAsyncIteration"}
    | {"CancelledError", "ImportError", "ModuleNotFoundError", "NameError", "KeyboardInterrupt", "EOFError", "Empty"}
    | {"QueueEmpty", "CancellationException", "OperationCanceledException", "TaskCanceledException"}
)
EXPECTED_EXCEPTION_SUFFIXES = ("NotFound", "NotFoundError", "DoesNotExist")

type Detector = Callable[[ParsedFile], Iterator[Finding]]

_DETECTORS: dict[str, Detector] = {}


def detects(*languages: str) -> Callable[[Detector], Detector]:
    return registering(_DETECTORS, *languages)


def swallow(parsed: ParsedFile, node: Node, severity: Severity, message: str) -> Finding:
    return Finding(parsed.path, line_of(node), RULE_ID, severity, message)


def normalized(node: Node) -> str:
    return " ".join((node_text(node) or "").split()).rstrip(";")


def statements_of(body: Node) -> list[Node]:
    return [child for child in body.named_children if child.type not in COMMENT_KINDS]


def body_text(body: Node) -> str | None:
    statements = statements_of(body)
    if len(statements) > 1:
        return None
    return normalized(statements[0]) if statements else ""


def is_logging_call(statement: Node) -> bool:
    expressions = statement.named_children if statement.type == EXPRESSION_STATEMENT else [statement]
    calls = [expression for expression in expressions if expression.type in CALL_KINDS]
    function = calls[0].child_by_field_name("function") if len(expressions) == 1 and calls else None
    return function is not None and LOGGING_FUNCTION.fullmatch(normalized(function)) is not None


def is_default_return(statement: str, defaults: frozenset[str]) -> bool:
    returned = statement.removeprefix(RETURN_KEYWORD)
    return statement in defaults or (returned != statement and DEFAULT_NAME.fullmatch(returned) is not None)


def logged_default(body: Node, defaults: frozenset[str]) -> str | None:
    *logs, last = statements_of(body) or [body]
    if not logs or not all(map(is_logging_call, logs)):
        return None
    result = normalized(last)
    return result if is_default_return(result, defaults) else None


def is_expected(name: str) -> bool:
    return name in EXPECTED_EXCEPTIONS or name.endswith(EXPECTED_EXCEPTION_SUFFIXES)


@cache
def load_detector_modules() -> None:
    import_package_modules(DETECTORS_PACKAGE)


def check_swallowed_failures(parsed: ParsedFile) -> list[Finding]:
    load_detector_modules()
    detector = _DETECTORS.get(parsed.language)
    return [] if detector is None else list(detector(parsed))


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Handlers that hide a failure: silent Python excepts, empty or empty-returning catches, "
            "and Go error checks that drop the error or return a nil error."
        ),
        run=check_swallowed_failures,
    )
)
