import re
from collections.abc import Iterator

from tree_sitter import Node

from pristine.calls import calls_of
from pristine.checks.unbounded_calls.calls import Violation
from pristine.parsing import ParsedFile, node_text
from pristine.python_calls import (
    EXTERNAL_CALLS,
    has_bound,
    import_bindings,
    keyword_values,
    positional_arguments,
    qualified_callee,
)

INTERACTIVE_PROGRAM = re.compile(r"\b(EDITOR|VISUAL|PAGER)\b|^[\"'](vi|vim|nvim|nano|emacs|less|more)[\"']$")
OUTPUT_CAPTURE_KEYWORDS = frozenset({"capture_output", "stdout", "stderr"})


def is_interactive_launch(qualified: str, arguments: list[Node]) -> bool:
    command = next(iter(positional_arguments(arguments)), None)
    if not qualified.startswith("subprocess.") or command is None or command.type != "list":
        return False
    program = node_text(command.named_children[0]) if command.named_children else None
    is_terminal_bound = keyword_values(arguments).keys().isdisjoint(OUTPUT_CAPTURE_KEYWORDS)
    return is_terminal_bound and INTERACTIVE_PROGRAM.search(program or "") is not None


def scan_python(parsed: ParsedFile) -> Iterator[Violation]:
    bindings = import_bindings(parsed.root)
    for node, callee, arguments in calls_of(parsed.root, "call"):
        qualified = qualified_callee(callee, bindings) or ""
        call = EXTERNAL_CALLS.get(qualified)
        if call is None or has_bound(arguments, call) or is_interactive_launch(qualified, arguments):
            continue
        yield Violation(node, callee, call)
