from collections.abc import Iterator

lazy from tree_sitter import Node

from pristine.clients.injection import RECEIVER, InjectedClient, called_injections, dotted_path
from pristine.clients.libraries import PYTHON_ENTRY_POINTS
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, node_text, typed_nodes
from pristine.syntax.python_calls import import_bindings, qualified_callee
from pristine.syntax.python_scopes import CLASS_KIND, ancestors, enclosing_functions, is_method, receiver_name

PARAMETER_KINDS = frozenset({"typed_parameter", "typed_default_parameter"})
WRAPPER_KINDS = frozenset({"type", "binary_operator"})
GENERIC_KIND = "generic_type"
OPTIONAL = "typing.Optional"


class PythonInjections:
    def __init__(self, source: Node | ParsedFile) -> None:
        self.bindings = import_bindings(source)

    def members(self, annotation: Node) -> list[Node]:
        if annotation.type in WRAPPER_KINDS:
            return [member for child in annotation.named_children for member in self.members(child)]
        head = annotation.named_children[0] if annotation.type == GENERIC_KIND else None
        if head is not None and qualified_callee(node_text(head) or "", self.bindings) == OPTIONAL:
            return [member for child in annotation.named_children[1:] for member in self.members(child)]
        return [] if annotation.type == "type_parameter" else [annotation]

    def entry_point(self, annotation: Node | None) -> str | None:
        members = [] if annotation is None else self.members(annotation)
        names = (qualified_callee(node_text(member) or "", self.bindings) for member in members)
        return next((name for name in names if name in PYTHON_ENTRY_POINTS), None)

    def parameters(self, parameter: Node) -> Iterator[InjectedClient]:
        name = parameter.child_by_field_name("name") or next(iter(parameter.named_children), None)
        function = parameter.parent.parent if parameter.parent is not None else None
        entry_point = self.entry_point(parameter.child_by_field_name("type"))
        if entry_point is None or function is None or name is None or name.type != "identifier":
            return
        yield InjectedClient(function, (node_text(name) or "",), entry_point, line_of(parameter))
        stores = receiver_stores(function)
        stored = ((owner, attribute) for owner, attribute, value in stores if node_text(value) == node_text(name))
        yield from (InjectedClient(owner, (RECEIVER, attr), entry_point, line_of(parameter)) for owner, attr in stored)

    def attributes(self, assignment: Node) -> Iterator[InjectedClient]:
        entry_point = self.entry_point(assignment.child_by_field_name("type"))
        attribute = attribute_target(assignment)
        if entry_point is not None and attribute is not None:
            yield InjectedClient(attribute[0], (RECEIVER, attribute[1]), entry_point, line_of(assignment))

    def injections(self, source: Node | ParsedFile) -> Iterator[InjectedClient]:
        for node in typed_nodes(source, *PARAMETER_KINDS, "assignment"):
            if node.type in PARAMETER_KINDS:
                yield from self.parameters(node)
            elif node.type == "assignment":
                yield from self.attributes(node)


def owning_class(node: Node) -> Node | None:
    return next((ancestor for ancestor in ancestors(node) if ancestor.type == CLASS_KIND), None)


def receiver_attribute(target: Node | None, function: Node) -> str | None:
    receiver = None if target is None else target.child_by_field_name("object")
    if target is None or target.type != "attribute" or receiver is None:
        return None
    return (
        node_text(target.child_by_field_name("attribute")) if node_text(receiver) == receiver_name(function) else None
    )


def receiver_stores(function: Node) -> Iterator[tuple[Node, str, Node | None]]:
    owner = owning_class(function) if is_method(function) else None
    assignments = (node for node in all_nodes(function) if node.type == "assignment") if owner is not None else ()
    for assignment in assignments:
        attribute = receiver_attribute(assignment.child_by_field_name("left"), function)
        if owner is not None and attribute is not None:
            yield owner, attribute, assignment.child_by_field_name("right")


def attribute_target(assignment: Node) -> tuple[Node, str] | None:
    left = assignment.child_by_field_name("left")
    function = next(enclosing_functions(assignment), None)
    if function is not None:
        attribute = receiver_attribute(left, function)
        owner = owning_class(function) if is_method(function) else None
        return None if attribute is None or owner is None else (owner, attribute)
    block = assignment.parent
    owner = block.parent if block is not None and block.type == "block" else None
    is_field = owner is not None and owner.type == CLASS_KIND and left is not None and left.type == "identifier"
    return (owner, node_text(left) or "") if is_field else None


def callee_paths(scope: Node) -> set[tuple[str, ...]]:
    calls = (node for node in all_nodes(scope) if node.type == "call")
    paths = set()
    for call in calls:
        path = dotted_path(call.child_by_field_name("function"))
        function = next(enclosing_functions(call), None)
        if path is not None and function is not None and path[0] == receiver_name(function):
            path = (RECEIVER, *path[1:])
        if path is not None:
            paths.add(path)
    return paths


def python_injected_clients(source: Node | ParsedFile) -> Iterator[tuple[str, int]]:
    return called_injections(PythonInjections(source).injections(source), callee_paths)
