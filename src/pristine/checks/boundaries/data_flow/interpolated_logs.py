import re

lazy from tree_sitter import Node

from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding, Severity
from pristine.syntax.nodes import COMMENT_KINDS
from pristine.syntax.parsing import ParsedFile, line_of, node_text
from pristine.syntax.python_strings import built_string

CHECK_ID = "SAFE-9"
LOGGER = re.compile(r"(.+\.)?_?(logger|log|LOGGER|LOG)|logging")
LOG_METHODS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical", "log"})
SCRIPT_LOGGER = re.compile(r"console|(.+\.)?_?(logger|log|LOGGER|LOG)")
LEVEL_METHOD = "log"
NON_MESSAGE_KINDS = COMMENT_KINDS | {"keyword_argument"}


def log_message(call: Node) -> Node | None:
    function = call.child_by_field_name("function")
    arguments = call.child_by_field_name("arguments")
    if function is None or arguments is None or function.type != "attribute":
        return None
    method = node_text(function.child_by_field_name("attribute")) or ""
    owner = node_text(function.child_by_field_name("object")) or ""
    if method not in LOG_METHODS or not LOGGER.fullmatch(owner):
        return None
    positional = [argument for argument in arguments.named_children if argument.type not in NON_MESSAGE_KINDS]
    position = int(method == LEVEL_METHOD)
    return positional[position] if len(positional) > position else None


def message_builder(call: Node) -> str | None:
    if call.type == "call_expression":
        return script_message_builder(call)
    message = log_message(call) if call.type == "call" else None
    built = None if message is None else built_string(message)
    return None if built is None else built.method


def is_script_concatenation(message: Node) -> bool:
    operator = node_text(message.child_by_field_name("operator"))
    operands = [message.child_by_field_name(field) for field in ("left", "right")]
    return operator == "+" and any(
        operand is not None and operand.type in {"string", "template_string"} for operand in operands
    )


def script_message_builder(call: Node) -> str | None:
    function = call.child_by_field_name("function")
    arguments = call.child_by_field_name("arguments")
    if function is None or function.type != "member_expression" or arguments is None:
        return None
    owner = node_text(function.child_by_field_name("object")) or ""
    method = node_text(function.child_by_field_name("property")) or ""
    if not SCRIPT_LOGGER.fullmatch(owner) or method not in LOG_METHODS:
        return None
    message = next((argument for argument in arguments.named_children if argument.type not in COMMENT_KINDS), None)
    if message is not None and message.type == "template_string":
        return (
            "template interpolation"
            if any(child.type == "template_substitution" for child in message.named_children)
            else None
        )
    if message is not None and message.type == "binary_expression":
        return "string concatenation" if is_script_concatenation(message) else None
    return None


def check_interpolated_logs(parsed: ParsedFile) -> list[Finding]:
    if parsed.language not in {"python", "javascript", "typescript", "tsx"}:
        return []
    built = [(node, message_builder(node)) for node in parsed.nodes_of("call", "call_expression")]
    return [
        Finding(
            parsed.path,
            line_of(node),
            CHECK_ID,
            Severity.WARNING,
            f"log message is built with {builder}; log a constant message and pass the values as arguments "
            "or structured fields, keeping personal data out",
        )
        for node, builder in built
        if builder is not None
    ]


CHECK = FileCheck(
    check_id=CHECK_ID,
    title="Constant Log Messages",
    summary=(
        "Python logging calls whose message is built by an f-string, %-formatting, str.format, or string "
        "concatenation, on logger, log, and logging."
        " JS/TS console, logger and log messages built with template interpolation or literal-string concatenation; "
        "constant messages, format placeholders and structured fields are exempt."
    ),
    run=check_interpolated_logs,
)
