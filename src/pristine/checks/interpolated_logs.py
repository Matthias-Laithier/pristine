import re
from collections.abc import Callable

from tree_sitter import Node

from pristine.checks.registry import FileCheck, register_file_check
from pristine.findings import Finding, Severity
from pristine.parsing import ParsedFile, all_nodes, line_of, node_text
from pristine.registration import registering
from pristine.syntax_kinds import COMMENT_KINDS

RULE_ID = "BS-15"
LOGGER = re.compile(r"(.+\.)?_?(logger|log|LOGGER|LOG)|logging")
LOG_METHODS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical", "log"})
LEVEL_METHOD = "log"
STRING_KINDS = frozenset({"string", "concatenated_string"})
NON_MESSAGE_KINDS = COMMENT_KINDS | {"keyword_argument"}
F_STRING = "an f-string"

type BuilderReader = Callable[[Node], str | None]

_BUILDERS: dict[str, BuilderReader] = {}


def is_interpolated(node: Node) -> bool:
    strings = node.named_children if node.type == "concatenated_string" else [node]
    return any(child.type == "interpolation" for string in strings for child in string.named_children)


def is_constant_string(node: Node) -> bool:
    return node.type in STRING_KINDS and not is_interpolated(node)


@registering(_BUILDERS, *STRING_KINDS)
def f_string_builder(node: Node) -> str | None:
    return F_STRING if is_interpolated(node) else None


@registering(_BUILDERS, "binary_operator")
def operator_builder(node: Node) -> str | None:
    operator = node_text(node.child_by_field_name("operator"))
    operands = [operand for operand in (node.child_by_field_name("left"), node.child_by_field_name("right")) if operand]
    if operator == "%" and operands[0].type in STRING_KINDS:
        return "%-formatting"
    is_text = any(operand.type in STRING_KINDS for operand in operands)
    if operator == "+" and is_text and not all(map(is_constant_string, operands)):
        return "string concatenation"
    return None


@registering(_BUILDERS, "call")
def format_builder(node: Node) -> str | None:
    function = node.child_by_field_name("function")
    if function is None or function.type != "attribute":
        return None
    owner = function.child_by_field_name("object")
    is_format = node_text(function.child_by_field_name("attribute")) == "format"
    return "str.format" if is_format and owner is not None and owner.type in STRING_KINDS else None


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
    builder = None if message is None else _BUILDERS.get(message.type)
    return None if builder is None or message is None else builder(message)


def check_interpolated_logs(parsed: ParsedFile) -> list[Finding]:
    if parsed.language != "python":
        return []
    built = [(node, message_builder(node)) for node in all_nodes(parsed.root)]
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
