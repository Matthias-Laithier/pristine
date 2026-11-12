lazy from tree_sitter import Node

from pristine.clients.libraries import SCRIPT_MODEL_CLIENTS
from pristine.clients.literals import string_content
from pristine.clients.script_calls import LEXICAL_SCOPES, bound_names
from pristine.clients.script_imports import import_bindings, is_type_only_import
from pristine.syntax.nodes import FUNCTION_KINDS
from pristine.syntax.parsing import ParsedFile, node_text

TYPE_WRAPPERS = frozenset({"parenthesized_expression", "as_expression", "satisfies_expression"})
SCOPE_KINDS = LEXICAL_SCOPES | FUNCTION_KINDS
DECLARATION_FIELDS = {
    "variable_declarator": "name",
    "required_parameter": "pattern",
    "optional_parameter": "pattern",
    "function_declaration": "name",
    "class_declaration": "name",
    "abstract_class_declaration": "name",
    "type_alias_declaration": "name",
    "interface_declaration": "name",
    "type_parameter": "name",
    "catch_clause": "parameter",
    "for_in_statement": "left",
    "function_expression": "name",
}
TYPE_DECLARATIONS = frozenset({"type_alias_declaration", "interface_declaration", "type_parameter"})


class ModelBindings:
    def __init__(self) -> None:
        self.values: dict[int, dict[str, Node]] = {}
        self.types: dict[int, dict[str, Node]] = {}
        self.runtime_imports: set[int] = set()
        self.type_imports: set[int] = set()
        self.assigned: set[int] = set()

    def resolve(self, use: Node, name: str, *, annotation: bool = False) -> Node | None:
        scopes = self.types if annotation else self.values
        holder: Node | None = use
        while holder is not None:
            binding = scopes.get(holder.id, {}).get(name)
            if binding is not None:
                return None if not annotation and binding.id in self.assigned else binding
            holder = holder.parent
        return None


def unwrapped(node: Node) -> Node:
    return unwrapped(node.named_children[0]) if node.type in TYPE_WRAPPERS and node.named_children else node


def declaration_scope(node: Node) -> Node:
    parent = node.parent
    function_local = (
        node.type in {"required_parameter", "optional_parameter", "type_parameter"}
        or (parent is not None and parent.type == "variable_declaration")
        or (node.type == "for_in_statement" and node_text(node.child_by_field_name("kind")) == "var")
    )
    kinds = FUNCTION_KINDS | {"program"} if function_local else SCOPE_KINDS
    while parent is not None and parent.type not in kinds:
        parent = parent.parent
    return node if parent is None else parent


def imported_bindings(statement: Node) -> list[tuple[str, Node]]:
    pairs = []
    items = [
        item
        for binding in import_bindings(statement)
        for item in (binding.named_children if binding.type == "named_imports" else [binding])
    ]
    for item in items:
        name = item.child_by_field_name("alias") or item.child_by_field_name("name")
        if item.type == "namespace_import":
            name = next(iter(item.named_children), None)
        pairs.append((node_text(name or item) or "", item))
    return pairs


def register_import(statement: Node, bindings: ModelBindings) -> None:
    owner = declaration_scope(statement).id
    model_sdk = string_content(statement.child_by_field_name("source")) in SCRIPT_MODEL_CLIENTS
    for name, node in imported_bindings(statement):
        bindings.types.setdefault(owner, {})[name] = node
        if model_sdk:
            bindings.type_imports.add(node.id)
        if is_type_only_import(statement) or is_type_only_import(node):
            continue
        bindings.values.setdefault(owner, {})[name] = node
        if model_sdk:
            bindings.runtime_imports.add(node.id)


def register_declaration(node: Node, bindings: ModelBindings) -> None:
    field = DECLARATION_FIELDS.get(node.type)
    names = bound_names(node.child_by_field_name(field)) if field is not None else set()
    if node.type in TYPE_DECLARATIONS | {"class_declaration", "abstract_class_declaration"}:
        names = {node_text(node.child_by_field_name("name")) or ""}
    if node.type in FUNCTION_KINDS:
        parameters = node.child_by_field_name("parameters")
        items = [] if parameters is None else parameters.named_children
        single = node.child_by_field_name("parameter")
        for parameter in items + ([] if single is None else [single]):
            bindings.values.setdefault(node.id, {}).update(dict.fromkeys(bound_names(parameter), parameter))
    if not names:
        return
    owns_binding = node.type in {"catch_clause", "function_expression"} or (
        node.type == "for_in_statement" and node_text(node.child_by_field_name("kind")) != "var"
    )
    owner = node if owns_binding or node.type in FUNCTION_KINDS and field is None else declaration_scope(node)
    tables = [bindings.types] if node.type in TYPE_DECLARATIONS else [bindings.values]
    if node.type in {"class_declaration", "abstract_class_declaration"}:
        tables.append(bindings.types)
    for table in tables:
        table.setdefault(owner.id, {}).update(dict.fromkeys(names, node))


def model_bindings(parsed: ParsedFile) -> ModelBindings:
    bindings = ModelBindings()
    for node in parsed.nodes:
        if node.type == "import_statement":
            register_import(node, bindings)
        else:
            register_declaration(node, bindings)
    assignments = parsed.nodes_of("assignment_expression", "augmented_assignment_expression", "update_expression")
    assigned = {
        declaration.id
        for node in assignments
        for name in bound_names(node.child_by_field_name("left") or node.child_by_field_name("argument"))
        if (declaration := bindings.resolve(node, name)) is not None
    }
    bindings.assigned = assigned
    return bindings


def literal_value(value: Node, bindings: ModelBindings) -> Node:
    value = unwrapped(value)
    if value.type not in {"identifier", "shorthand_property_identifier"}:
        return value
    declaration = bindings.resolve(value, node_text(value) or "")
    name = None if declaration is None else declaration.child_by_field_name("name")
    if name is None or name.type != "identifier":
        return value
    initializer = None if declaration is None else declaration.child_by_field_name("value")
    return value if initializer is None else unwrapped(initializer)


def imported_reference(node: Node, bindings: ModelBindings, *, annotation: bool = False) -> bool:
    head = (node_text(node) or "").split(".")[0]
    declaration = bindings.resolve(node, head, annotation=annotation)
    imports = bindings.type_imports if annotation else bindings.runtime_imports
    return declaration is not None and declaration.id in imports


def sdk_annotation(node: Node, bindings: ModelBindings) -> bool:
    if node.type in {"type_identifier", "nested_type_identifier"}:
        return imported_reference(node, bindings, annotation=True)
    if node.type not in {"type_annotation", "union_type", "parenthesized_type"}:
        return False
    return any(sdk_annotation(child, bindings) for child in node.named_children)


def model_client(call: Node, bindings: ModelBindings) -> bool:
    function = call.child_by_field_name("function")
    if function is None:
        return False
    if imported_reference(function, bindings):
        return True
    head = (node_text(function) or "").split(".")[0]
    declaration = bindings.resolve(call, head)
    pattern = (
        None
        if declaration is None
        else declaration.child_by_field_name("name") or declaration.child_by_field_name("pattern")
    )
    if pattern is None or pattern.type != "identifier":
        return False
    annotation = None if declaration is None else declaration.child_by_field_name("type")
    if annotation is not None and sdk_annotation(annotation, bindings):
        return True
    value = None if declaration is None else declaration.child_by_field_name("value")
    value = None if value is None else unwrapped(value)
    constructor = (
        None if value is None else value.child_by_field_name("constructor") or value.child_by_field_name("function")
    )
    return constructor is not None and imported_reference(constructor, bindings)
