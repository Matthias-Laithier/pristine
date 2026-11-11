from collections.abc import Iterator
from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.clients.script_calls import bound_names, function_var_names
from pristine.clients.script_calls import local_nodes as lexical_nodes
from pristine.syntax.calls import callee_of, calls_of
from pristine.syntax.nodes import FUNCTION_KINDS
from pristine.syntax.parsing import ParsedFile, all_nodes, node_text

LEXICAL_SCOPES = frozenset({"statement_block", "catch_clause", "for_statement", "for_in_statement"})
SCOPES = FUNCTION_KINDS | LEXICAL_SCOPES | {"program"}
FRAMEWORKS = frozenset({"vitest", "@jest/globals"})
GLOBALS = frozenset({"test", "it", "expect", "vi", "jest", "describe", "beforeEach", "beforeAll", "Math", "setTimeout"})
TEST_NAMES = frozenset({"test", "it"})


def parents(node: Node) -> Iterator[Node]:
    holder = node.parent
    while holder is not None:
        yield holder
        holder = holder.parent


def local_nodes(scope: Node) -> Iterator[Node]:
    pending = list(reversed(scope.named_children))
    while pending:
        node = pending.pop()
        yield node
        if node.type not in SCOPES:
            pending.extend(reversed(node.named_children))


def import_member(child: Node, name: str, module: str) -> str | None:
    if child.type == "import_specifier":
        original = child.child_by_field_name("name")
        alias = child.child_by_field_name("alias") or original
        return f"{module}.{node_text(original)}" if node_text(alias) == name else None
    kinds = {"namespace_import", "import_clause"}
    if child.type in kinds and any(
        item.type == "identifier" and node_text(item) == name for item in child.named_children
    ):
        return module
    return None


def imported_name(node: Node, name: str) -> str | None:
    module = (node_text(node.child_by_field_name("source")) or "").strip("\"'")
    return next((value for child in all_nodes(node) if (value := import_member(child, name, module)) is not None), None)


def binds(node: Node, name: str) -> bool:
    field = "name" if node.type in {"variable_declarator", "function_declaration", "class_declaration"} else ""
    target = node.child_by_field_name(field)
    if node.type in {"required_parameter", "optional_parameter"}:
        target = node.child_by_field_name("pattern")
    if node.type == "arrow_function":
        target = node.child_by_field_name("parameter")
    if node.type == "catch_clause":
        target = node.child_by_field_name("parameter")
    if node.type == "for_in_statement" and node_text(node.child_by_field_name("kind")) in {"let", "const"}:
        target = node.child_by_field_name("left")
    if node.type in {"assignment_expression", "augmented_assignment_expression"}:
        target = node.child_by_field_name("left")
        return target is not None and target.type == "identifier" and node_text(target) == name
    return name in bound_names(target)


def scope_binding(scope: Node, name: str) -> tuple[bool, str | None]:
    if binds(scope, name):
        return True, None
    nodes = list(local_nodes(scope))
    if any(binds(node, name) for node in nodes if node.type not in LEXICAL_SCOPES):
        return True, None
    if scope.type in FUNCTION_KINDS | {"program"} and any(
        name in function_var_names(node) for node in lexical_nodes(scope, include_blocks=True)
    ):
        return True, None
    for node in nodes:
        if node.type == "import_statement" and (value := imported_name(node, name)) is not None:
            return True, value
    return False, None


def resolve(name: str, at: Node) -> str | None:
    for scope in (holder for holder in parents(at) if holder.type in SCOPES):
        found, value = scope_binding(scope, name)
        if found:
            return value
    return name if name in GLOBALS else None


def qualified(call: Node) -> str:
    callee = callee_of(call)
    head, separator, tail = callee.partition(".")
    binding = resolve(head, call)
    return f"{binding}{separator}{tail}" if binding is not None else ""


def framework_call(call: Node, names: frozenset[str]) -> bool:
    name = qualified(call)
    parts = name.split(".")
    if parts[0] in FRAMEWORKS:
        parts = parts[1:]
    return (
        bool(parts)
        and parts[0] in names
        and all(part in {"only", "skip", "todo", "concurrent", "sequential"} for part in parts[1:])
    )


def callback(call: Node) -> Node | None:
    arguments = call.child_by_field_name("arguments")
    if arguments is None:
        return None
    return next((node for node in reversed(arguments.named_children) if node.type in FUNCTION_KINDS), None)


def test_callbacks(parsed: ParsedFile) -> list[Node]:
    if parsed.language not in {"javascript", "typescript", "tsx"} or not PurePath(parsed.path).name.endswith(
        (
            ".test.ts",
            ".spec.ts",
            ".test.tsx",
            ".spec.tsx",
            ".test.js",
            ".spec.js",
            ".test.jsx",
            ".spec.jsx",
            ".test.mts",
            ".spec.mts",
            ".test.cts",
            ".spec.cts",
        )
    ):
        return []
    return [
        body
        for call, _, _ in calls_of(parsed, "call_expression")
        if framework_call(call, TEST_NAMES) and (body := callback(call)) is not None
    ]


def owned_calls(scope: Node) -> Iterator[Node]:
    for node in local_nodes(scope):
        if node.type in LEXICAL_SCOPES:
            yield from owned_calls(node)
        elif node.type == "call_expression":
            yield node
