from collections.abc import Iterator

from tree_sitter import Node

from pristine.checks.boundaries.execution.unbounded_calls.calls import Violation
from pristine.reports.findings import Severity
from pristine.syntax.calls import BoundedCall
from pristine.syntax.parsing import ParsedFile, all_nodes, node_text

HTTP_IMPORT = '"net/http"'
CLIENT = "http.Client"
DEFAULT_CLIENT = "http.DefaultClient"
TIMEOUT_FIELD = "Timeout"
CLIENT_FIX = "use an http.Client with Timeout set, or send a request whose context has a deadline"
UNBOUNDED_FUNCTIONS = frozenset({"http.Get", "http.Head", "http.Post", "http.PostForm"})
FUNCTION_CALL = BoundedCall(TIMEOUT_FIELD, None, Severity.ERROR, CLIENT_FIX)
DEFAULT_CLIENT_USE = BoundedCall(TIMEOUT_FIELD, None, Severity.WARNING, CLIENT_FIX)
CLIENT_LITERAL = BoundedCall(
    TIMEOUT_FIELD, None, Severity.WARNING, "set Timeout, or give every request a context deadline"
)


def client_keys(literal: Node) -> list[str | None]:
    body = literal.child_by_field_name("body")
    return [node_text(element.child_by_field_name("key")) for element in (body.named_children if body else [])]


def node_violation(node: Node) -> Violation | None:
    callee = node_text(node.child_by_field_name("function")) if node.type == "call_expression" else None
    if callee in UNBOUNDED_FUNCTIONS:
        return Violation(node, callee or "", FUNCTION_CALL)
    if node.type == "selector_expression" and node_text(node) == DEFAULT_CLIENT:
        return Violation(node, DEFAULT_CLIENT, DEFAULT_CLIENT_USE)
    is_client = node.type == "composite_literal" and node_text(node.child_by_field_name("type")) == CLIENT
    if is_client and TIMEOUT_FIELD not in client_keys(node):
        return Violation(node, CLIENT, CLIENT_LITERAL)
    return None


def scan_go(parsed: ParsedFile) -> Iterator[Violation]:
    if HTTP_IMPORT not in parsed.text:
        return
    violations = (node_violation(node) for node in all_nodes(parsed.root))
    yield from (violation for violation in violations if violation is not None)
