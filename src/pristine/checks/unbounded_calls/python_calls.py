import re
from collections.abc import Iterator

from tree_sitter import Node

from pristine.checks.unbounded_calls.calls import BoundedCall, Violation, calls_of, has_unknown_argument
from pristine.findings import Severity
from pristine.parsing import ParsedFile, all_nodes, node_text

DOTTED_CALLEE = re.compile(r"[A-Za-z_][\w.]*(\(\)\.\w+)?")
TIMEOUT_FIX = "pass timeout=<seconds> sized to the operation's latency budget"
HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options", "request")
SUBPROCESS_FUNCTIONS = ("run", "call", "check_call", "check_output")
INTERACTIVE_PROGRAM = re.compile(r"\b(EDITOR|VISUAL|PAGER)\b|^[\"'](vi|vim|nvim|nano|emacs|less|more)[\"']$")
OUTPUT_CAPTURE_KEYWORDS = frozenset({"capture_output", "stdout", "stderr"})
KEYWORD_TIMEOUT = BoundedCall("timeout", None, Severity.ERROR, TIMEOUT_FIX)
PYTHON_CALLS = {
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
    local = alias or (imported if prefix else imported.split(".")[0])
    return local, prefix + (imported if prefix or alias else local)


def qualified_callee(callee: str, bindings: dict[str, str]) -> str | None:
    head, dot, rest = callee.partition(".")
    if not DOTTED_CALLEE.fullmatch(callee) or head not in bindings:
        return None
    return bindings[head] + dot + rest


def has_bound(arguments: list[Node], call: BoundedCall) -> bool:
    keywords = {node_text(argument.child_by_field_name("name")): argument for argument in arguments}
    bound = keywords.get(call.bound)
    if bound is not None:
        return node_text(bound.child_by_field_name("value")) != "None"
    positional_count = sum(1 for argument in arguments if argument.type != "keyword_argument")
    has_positional_bound = call.position is not None and positional_count > call.position
    return has_positional_bound or has_unknown_argument(arguments)


def is_interactive_launch(qualified: str, arguments: list[Node]) -> bool:
    command = next((argument for argument in arguments if argument.type != "keyword_argument"), None)
    if not qualified.startswith("subprocess.") or command is None or command.type != "list":
        return False
    keywords = {node_text(argument.child_by_field_name("name")) for argument in arguments}
    program = node_text(command.named_children[0]) if command.named_children else None
    is_terminal_bound = keywords.isdisjoint(OUTPUT_CAPTURE_KEYWORDS)
    return is_terminal_bound and INTERACTIVE_PROGRAM.search(program or "") is not None


def scan_python(parsed: ParsedFile) -> Iterator[Violation]:
    bindings = import_bindings(parsed.root)
    for node, callee, arguments in calls_of(parsed.root, "call"):
        qualified = qualified_callee(callee, bindings) or ""
        call = PYTHON_CALLS.get(qualified)
        if call is None or has_bound(arguments, call) or is_interactive_launch(qualified, arguments):
            continue
        yield Violation(node, callee, call)
