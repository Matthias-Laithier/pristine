import re

lazy from tree_sitter import Node

from pristine.checks.registry import FileCheck, register_file_check
from pristine.reports.findings import Finding, Severity
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text
from pristine.syntax.python_strings import built_string
from pristine.syntax.syntax_kinds import COMMENT_KINDS

RULE_ID = "BS-15"
LOGGER = re.compile(r"(.+\.)?_?(logger|log|LOGGER|LOG)|logging")
LOG_METHODS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical", "log"})
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
    message = log_message(call) if call.type == "call" else None
    built = None if message is None else built_string(message)
    return None if built is None else built.method


def check_interpolated_logs(parsed: ParsedFile) -> list[Finding]:
    if parsed.language != "python":
        return []
    built = [(node, message_builder(node)) for node in all_nodes(parsed)]
    return [
        Finding(
            parsed.path,
            line_of(node),
            RULE_ID,
            Severity.WARNING,
            f"log message is built with {builder}; log a constant message and pass the values as arguments "
            "or structured fields, keeping personal data out",
        )
        for node, builder in built
        if builder is not None
    ]


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Python logging calls whose message is built by an f-string, %-formatting, str.format, or string "
            "concatenation, on logger, log, and logging."
        ),
        run=check_interpolated_logs,
    )
)
