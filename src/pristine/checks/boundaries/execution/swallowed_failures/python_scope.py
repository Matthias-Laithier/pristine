from collections import Counter

lazy from tree_sitter import Node

from pristine.checks.boundaries.execution.swallowed_failures import HandlerScope, callee_text, normalized
from pristine.syntax.parsing import ParsedFile, all_nodes, module_statements, node_text, root_of
from pristine.syntax.python_calls import import_bindings, qualified_callee
from pristine.syntax.python_scopes import all_parameter_names

LOGGING_LEVELS = ("debug", "info", "warning", "warn", "error", "exception", "critical", "fatal", "log")
LOGGING_FUNCTIONS = frozenset(f"logging.{level}" for level in LOGGING_LEVELS)
LOGGER_FACTORIES = frozenset(
    {"logging.getLogger", "structlog.get_logger", "structlog.getLogger", "structlog.stdlib.get_logger"}
)
LOGGER_OBJECTS = frozenset({"loguru.logger"})
LOGGER_DERIVATIONS = frozenset({"bind", "new", "opt", "getChild"})
PRINT = "print"
DEFINITION_KINDS = frozenset({"function_definition", "class_definition"})


class LoggerResolver:
    def __init__(self, source: Node | ParsedFile) -> None:
        reassigned = {target for target, _ in assignments(source)}
        shadowed = reassigned | set(all_parameter_names(root_of(source)))
        self.bindings = {name: module for name, module in import_bindings(source).items() if name not in shadowed}
        self.loggers: set[str] = set()

    def qualified(self, node: Node) -> str:
        return qualified_callee(callee_text(node), self.bindings) or ""

    def is_logger(self, node: Node) -> bool:
        if node.type != "call":
            return callee_text(node) in self.loggers or self.qualified(node) in LOGGER_OBJECTS
        function = node.child_by_field_name("function")
        if function is None:
            return False
        if self.qualified(function) in LOGGER_FACTORIES:
            return True
        receiver = function.child_by_field_name("object") if function.type == "attribute" else None
        method = node_text(function.child_by_field_name("attribute"))
        return receiver is not None and method in LOGGER_DERIVATIONS and self.is_logger(receiver)

    def is_logging_callee(self, function: Node) -> bool:
        if self.qualified(function) in LOGGING_FUNCTIONS:
            return True
        receiver = function.child_by_field_name("object") if function.type == "attribute" else None
        return receiver is not None and self.is_logger(receiver)


def assignments(source: Node | ParsedFile) -> list[tuple[str, Node]]:
    pairs = (
        (node.child_by_field_name("left"), node.child_by_field_name("right"))
        for node in all_nodes(source)
        if node.type == "assignment"
    )
    return [(callee_text(left), right) for left, right in pairs if left is not None and right is not None]


def resolved_loggers(resolver: LoggerResolver, source: Node | ParsedFile) -> set[str]:
    pairs = assignments(source)
    changed = True
    while changed:
        found = {target for target, value in pairs if resolver.is_logger(value)}
        changed = not found <= resolver.loggers
        resolver.loggers |= found
    rebound = {target for target, value in pairs if not resolver.is_logger(value)} | set(
        all_parameter_names(root_of(source))
    )
    return resolver.loggers - rebound


def print_is_builtin(source: Node | ParsedFile, bindings: dict[str, str]) -> bool:
    definitions = (
        node_text(node.child_by_field_name("name")) for node in all_nodes(source) if node.type in DEFINITION_KINDS
    )
    assigned = (target for target, _ in assignments(source))
    return PRINT not in bindings and PRINT not in {*definitions, *assigned, *all_parameter_names(root_of(source))}


def logging_callees(source: Node | ParsedFile) -> frozenset[str]:
    resolver = LoggerResolver(source)
    resolver.loggers = resolved_loggers(resolver, source)
    functions = (node.child_by_field_name("function") for node in all_nodes(source) if node.type == "call")
    callees = {callee_text(function) for function in functions if function and resolver.is_logging_callee(function)}
    if print_is_builtin(source, resolver.bindings):
        callees.add(PRINT)
    return frozenset(callees)


def default_constants(source: Node | ParsedFile, default_values: frozenset[str]) -> frozenset[str]:
    statements = (statement for statement in module_statements(root_of(source)) if statement.type == "assignment")
    pairs = (
        (statement.child_by_field_name("left"), statement.child_by_field_name("right")) for statement in statements
    )
    bound = Counter([target for target, _ in assignments(source)] + list(all_parameter_names(root_of(source))))
    return frozenset(
        node_text(left) or ""
        for left, right in pairs
        if left is not None
        and left.type == "identifier"
        and right is not None
        and normalized(right) in default_values
        and bound[node_text(left) or ""] == 1
    )


def python_scope(source: Node | ParsedFile, default_values: frozenset[str]) -> HandlerScope:
    return HandlerScope(logging_callees(source), default_constants(source, default_values))
