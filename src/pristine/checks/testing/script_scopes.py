from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.clients.script_calls import bound_names, function_var_names
from pristine.clients.script_calls import local_nodes as lexical_nodes
from pristine.syntax.calls import callee_of, calls_of
from pristine.syntax.nodes import FUNCTION_KINDS, SyntaxNode
from pristine.syntax.parsing import ParsedFile, all_nodes, node_text

LEXICAL_SCOPES = frozenset({"statement_block", "catch_clause", "for_statement", "for_in_statement"})
SCOPES = FUNCTION_KINDS | LEXICAL_SCOPES | {"program"}
FRAMEWORKS = frozenset({"vitest", "@jest/globals"})
GLOBALS = frozenset({"test", "it", "expect", "vi", "jest", "describe", "beforeEach", "beforeAll", "Math", "setTimeout"})
TEST_NAMES = frozenset({"test", "it"})
MODIFIERS = frozenset({"only", "skip", "todo", "concurrent", "sequential"})


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


def import_members(child: Node, module: str) -> Iterator[tuple[str | None, str]]:
    if child.type == "import_specifier":
        original = child.child_by_field_name("name")
        yield node_text(child.child_by_field_name("alias") or original), f"{module}.{node_text(original)}"
    elif child.type in {"namespace_import", "import_clause"}:
        yield from ((node_text(item), module) for item in child.named_children if item.type == "identifier")


def imported_names(node: Node) -> dict[str, str]:
    module = (node_text(node.child_by_field_name("source")) or "").strip("\"'")
    members: dict[str, str] = {}
    for name, value in (member for child in all_nodes(node) for member in import_members(child, module)):
        if name is not None:
            members.setdefault(name, value)
    return members


def bound_by(node: Node) -> set[str]:
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
        name = None if target is None or target.type != "identifier" else node_text(target)
        return set() if name is None else {name}
    return bound_names(target)


def scope_bindings(scope: Node) -> dict[str, str | None]:
    nodes = list(local_nodes(scope))
    imports: dict[str, str | None] = {}
    for statement in (node for node in nodes if node.type == "import_statement"):
        imports = imported_names(statement) | imports
    local = bound_by(scope)
    for node in nodes:
        if node.type not in LEXICAL_SCOPES:
            local |= bound_by(node)
    if scope.type in FUNCTION_KINDS | {"program"}:
        for node in lexical_nodes(scope, include_blocks=True):
            local |= function_var_names(node)
    return imports | {name: None for name in local}


class ScriptResolution:
    def __init__(self) -> None:
        self.scopes: dict[Node, dict[str, str | None]] = {}
        self.calls: dict[Node, str] = {}

    def binding(self, scope: Node, name: str) -> tuple[bool, str | None]:
        if scope not in self.scopes:
            self.scopes[scope] = scope_bindings(scope)
        bindings = self.scopes[scope]
        return (True, bindings[name]) if name in bindings else (False, None)

    def qualified(self, call: Node) -> str:
        if call not in self.calls:
            self.calls[call] = qualified(call, self)
        return self.calls[call]


def resolve(name: str, at: Node, resolution: ScriptResolution) -> str | None:
    for scope in (holder for holder in parents(at) if holder.type in SCOPES):
        found, value = resolution.binding(scope, name)
        if found:
            return value
    return name if name in GLOBALS else None


def qualified(call: Node, resolution: ScriptResolution) -> str:
    callee = callee_of(call)
    head, separator, tail = callee.partition(".")
    binding = resolve(head, call, resolution)
    return f"{binding}{separator}{tail}" if binding is not None else ""


def framework_call(call: Node, names: frozenset[str], resolution: ScriptResolution) -> bool:
    _, separator, tail = callee_of(call).partition(".")
    members = tail.split(".") if separator else []
    if members and (members[0] not in names | MODIFIERS or not MODIFIERS.issuperset(members[1:])):
        return False
    name = resolution.qualified(call)
    parts = name.split(".")
    if parts[0] in FRAMEWORKS:
        parts = parts[1:]
    return bool(parts) and parts[0] in names and MODIFIERS.issuperset(parts[1:])


def callback(call: Node) -> Node | None:
    arguments = call.child_by_field_name("arguments")
    if arguments is None:
        return None
    return next((node for node in reversed(arguments.named_children) if node.type in FUNCTION_KINDS), None)


def test_callbacks(parsed: ParsedFile, resolution: ScriptResolution) -> list[Node]:
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
        if framework_call(call, TEST_NAMES, resolution) and (body := callback(call)) is not None
    ]


@dataclass(frozen=True)
class ScriptTests:
    resolution: ScriptResolution
    callbacks: list[SyntaxNode]


def resolved_tests(parsed: ParsedFile) -> ScriptTests:
    resolution = ScriptResolution()
    return ScriptTests(resolution, test_callbacks(parsed, resolution))


def script_tests(parsed: ParsedFile) -> ScriptTests:
    return parsed.shared(ScriptTests, resolved_tests)


def owned_calls(scope: Node) -> Iterator[Node]:
    for node in local_nodes(scope):
        if node.type in LEXICAL_SCOPES:
            yield from owned_calls(node)
        elif node.type == "call_expression":
            yield node
