from collections.abc import Iterator

from tree_sitter import Node

from pristine.checks.testing.model_clients_in_tests.live_clients import LiveClient, all_environment_reads, is_within
from pristine.clients.libraries import PYTHON_MODEL_CLIENTS
from pristine.syntax.calls import callee_of
from pristine.syntax.parsing import all_nodes, line_of, node_text
from pristine.syntax.python_calls import import_bindings, keyword_values, qualified_callee
from pristine.syntax.python_strings import is_constant_string

API_KEY_ARGUMENT = "api_key"
ENVIRONMENT_READERS = frozenset({"os.getenv", "os.environ.get"})
ENVIRONMENT = "os.environ"


class PythonEnvironment:
    def __init__(self, root: Node) -> None:
        self.bindings = import_bindings(root)
        assignments = (node for node in all_nodes(root) if node.type == "assignment")
        self.assigned: dict[str, list[Node]] = {}
        for assignment in assignments:
            value = assignment.child_by_field_name("right")
            if value is not None:
                self.assigned.setdefault(node_text(assignment.child_by_field_name("left")) or "", []).append(value)

    def read_key(self, value: Node) -> tuple[bool, str | None]:
        if value.type == "identifier":
            sources = self.assigned.get(node_text(value) or "", [])
            reads = [self.read_key(source) for source in sources if source.type != "identifier"]
            return all_environment_reads(reads)
        if value.type == "subscript":
            container, key = value.child_by_field_name("value"), value.child_by_field_name("subscript")
            is_read = (
                container is not None and qualified_callee(node_text(container) or "", self.bindings) == ENVIRONMENT
            )
            return is_read, key_name(key)
        arguments = value.child_by_field_name("arguments")
        if value.type != "call" or arguments is None:
            return False, None
        is_read = qualified_callee(callee_of(value), self.bindings) in ENVIRONMENT_READERS
        return is_read, key_name(next(iter(arguments.named_children), None))

    def is_model_client(self, call: Node) -> bool:
        return is_within(qualified_callee(callee_of(call), self.bindings) or "", PYTHON_MODEL_CLIENTS, ".")


def key_name(node: Node | None) -> str | None:
    return (node_text(node) or "").strip("'\"") if node is not None and is_constant_string(node) else None


def python_live_clients(root: Node) -> Iterator[LiveClient]:
    environment = PythonEnvironment(root)
    for call in (node for node in all_nodes(root) if node.type == "call" and environment.is_model_client(node)):
        arguments = call.child_by_field_name("arguments")
        key = None if arguments is None else keyword_values(arguments.named_children).get(API_KEY_ARGUMENT)
        is_read, name = (False, None) if key is None else environment.read_key(key)
        if is_read:
            yield LiveClient(line_of(call), name)
