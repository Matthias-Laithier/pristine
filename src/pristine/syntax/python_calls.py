import re

from tree_sitter import Node

from pristine.reports.findings import Severity
from pristine.syntax.calls import BoundedCall, has_unknown_argument
from pristine.syntax.parsing import all_nodes, node_text

DOTTED_CALLEE = re.compile(r"[A-Za-z_][\w.]*(\(\)\.\w+)?")
KEYWORD_ARGUMENT_KIND = "keyword_argument"
TIMEOUT_FIX = "pass timeout=<seconds> sized to the operation's latency budget"
HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options", "request")
SUBPROCESS_FUNCTIONS = ("run", "call", "check_call", "check_output")
KEYWORD_TIMEOUT = BoundedCall("timeout", None, Severity.ERROR, TIMEOUT_FIX)
EXTERNAL_CALLS = {
    **{f"requests.{method}": KEYWORD_TIMEOUT for method in HTTP_METHODS},
    **{f"requests.Session().{method}": KEYWORD_TIMEOUT for method in HTTP_METHODS},
    **{f"subprocess.{function}": KEYWORD_TIMEOUT for function in SUBPROCESS_FUNCTIONS},
    "urllib.request.urlopen": BoundedCall("timeout", 2, Severity.ERROR, TIMEOUT_FIX),
    "socket.create_connection": BoundedCall("timeout", 1, Severity.ERROR, TIMEOUT_FIX),
    "smtplib.SMTP": BoundedCall("timeout", 3, Severity.ERROR, TIMEOUT_FIX),
    "smtplib.SMTP_SSL": BoundedCall("timeout", 3, Severity.ERROR, TIMEOUT_FIX),
}


def import_bindings(root: Node) -> dict[str, str]:
    bindings = {}
    for node in all_nodes(root):
        module = node.child_by_field_name("module_name")
        is_absolute_from = node.type == "import_from_statement" and module is not None and module.type == "dotted_name"
        prefix = f"{node_text(module)}." if is_absolute_from else ""
        names = node.children_by_field_name("name") if node.type == "import_statement" or is_absolute_from else []
        bindings.update(import_binding(name, prefix) for name in names)
    return bindings


def import_binding(name: Node, prefix: str) -> tuple[str, str]:
    alias = node_text(name.child_by_field_name("alias"))
    imported = node_text(name.child_by_field_name("name")) or node_text(name) or ""
    local = alias if alias is not None else (imported if prefix else imported.split(".")[0])
    return local, prefix + (imported if prefix or alias is not None else local)


def qualified_callee(callee: str, bindings: dict[str, str]) -> str | None:
    head, dot, rest = callee.partition(".")
    if not DOTTED_CALLEE.fullmatch(callee) or head not in bindings:
        return None
    return bindings[head] + dot + rest


def positional_arguments(arguments: list[Node]) -> list[Node]:
    return [argument for argument in arguments if argument.type != KEYWORD_ARGUMENT_KIND]


def keyword_values(arguments: list[Node]) -> dict[str, Node]:
    keywords = (argument for argument in arguments if argument.type == KEYWORD_ARGUMENT_KIND)
    return {
        node_text(keyword.child_by_field_name("name")) or "": keyword.child_by_field_name("value") or keyword
        for keyword in keywords
    }


def has_bound(arguments: list[Node], call: BoundedCall) -> bool:
    bound = keyword_values(arguments).get(call.bound)
    if bound is not None:
        return node_text(bound) != "None"
    has_positional_bound = call.position is not None and len(positional_arguments(arguments)) > call.position
    return has_positional_bound or has_unknown_argument(arguments)
