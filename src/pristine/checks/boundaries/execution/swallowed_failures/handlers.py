from dataclasses import dataclass

lazy from tree_sitter import Node

from pristine.reports.findings import Finding, Severity
from pristine.syntax.nodes import COMMENT_KINDS
from pristine.syntax.parsing import ParsedFile, line_of, node_text

RULE_ID = "BS-4"
PROPAGATE_HINT = "handle it, translate it while keeping the cause, or let it propagate"
NARROW_HINT = "narrow the catch to the expected error, or let the failure propagate"
CALL_KINDS = frozenset({"call", "call_expression"})
RETURN_KEYWORD = "return "
EXPRESSION_STATEMENT = "expression_statement"
EXPECTED_EXCEPTIONS = frozenset(
    {"FileNotFoundError", "FileExistsError", "ProcessLookupError", "StopIteration", "StopAsyncIteration"}
    | {"CancelledError", "ImportError", "ModuleNotFoundError", "NameError", "KeyboardInterrupt", "EOFError", "Empty"}
    | {"QueueEmpty"}
)
FAILING_ASSERTIONS = frozenset({"fail", "pytest.fail"})
ASSERTION_CATCHERS = frozenset({"", "BaseException", "AssertionError"})
ASSERTION_CALL_KINDS = frozenset({"call", "call_expression"})
ATTEMPT_BODY_KINDS = frozenset({"block"})


@dataclass(frozen=True)
class HandlerScope:
    logging_callees: frozenset[str]
    default_constants: frozenset[str]


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


def is_logging_call(statement: Node, scope: HandlerScope) -> bool:
    expressions = statement.named_children if statement.type == EXPRESSION_STATEMENT else [statement]
    calls = [expression for expression in expressions if expression.type in CALL_KINDS]
    function = calls[0].child_by_field_name("function") if len(expressions) == 1 and calls else None
    return function is not None and callee_text(function) in scope.logging_callees


def callee_text(function: Node) -> str:
    return "".join((node_text(function) or "").split())


def returned_values(defaults: frozenset[str]) -> frozenset[str]:
    return frozenset(default.removeprefix(RETURN_KEYWORD) for default in defaults if default.startswith(RETURN_KEYWORD))


def is_default_return(statement: str, defaults: frozenset[str], scope: HandlerScope) -> bool:
    returned = statement.removeprefix(RETURN_KEYWORD)
    return statement in defaults or (returned != statement and returned in scope.default_constants)


def logged_default(body: Node, defaults: frozenset[str], scope: HandlerScope) -> str | None:
    *logs, last = statements_of(body) or [body]
    if not logs or not all(is_logging_call(log, scope) for log in logs):
        return None
    result = normalized(last)
    return result if is_default_return(result, defaults, scope) else None


def is_expected(name: str) -> bool:
    return name in EXPECTED_EXCEPTIONS


def asserts_failure(clause: Node, names: frozenset[str]) -> bool:
    attempt = clause.parent
    bodies = [] if attempt is None else [child for child in attempt.named_children if child.type in ATTEMPT_BODY_KINDS]
    statements = statements_of(bodies[0]) if bodies else []
    last = statements[-1] if statements else None
    call = last.named_children[0] if last is not None and last.type == EXPRESSION_STATEMENT else last
    is_fail_call = call is not None and call.type in ASSERTION_CALL_KINDS
    return is_fail_call and normalized(call).split("(", 1)[0] in FAILING_ASSERTIONS and not names & ASSERTION_CATCHERS
