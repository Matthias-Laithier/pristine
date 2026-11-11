from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.checks.composition.parameter_mutation.python import CHECK_ID, MESSAGE
from pristine.checks.composition.parameter_mutation.types import COLLECTION_TYPES, MUTATORS, typed_parameters
from pristine.clients.script_calls import bound_names
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.syntax.nodes import FUNCTION_KINDS
from pristine.syntax.parsing import ParsedFile, all_nodes, function_name, line_of, node_text, unwrapped
from pristine.syntax.python_scopes import own_nodes

SCOPES = FUNCTION_KINDS | {"class_declaration", "class", "abstract_class_declaration"}
WRITES = {"assignment_expression": "left", "augmented_assignment_expression": "left", "update_expression": "argument"}
BINDINGS = {"variable_declarator": "name", "for_in_statement": "left", "catch_clause": "parameter"} | WRITES
DECLARATIONS = {
    "variable_declarator": "name",
    "function_declaration": "name",
    "class_declaration": "name",
    "abstract_class_declaration": "name",
    "type_alias_declaration": "name",
    "interface_declaration": "name",
    "enum_declaration": "name",
    "type_parameter": "name",
    "required_parameter": "pattern",
    "optional_parameter": "pattern",
    "import_specifier": "alias",
}


def assigned_function(member: Node) -> Node | None:
    value = member.child_by_field_name("value")
    name = member.child_by_field_name("name")
    is_function = value is not None and value.type in {"arrow_function", "function_expression"}
    return value if is_function and name is not None and name.type == "identifier" else None


def declaration_functions(declaration: Node) -> list[Node]:
    if declaration.type == "function_declaration":
        return [declaration]
    if declaration.type not in {"lexical_declaration", "variable_declaration"}:
        return []
    functions = map(assigned_function, declaration.named_children)
    return [function for function in functions if function is not None]


def module_functions(parsed: ParsedFile) -> list[Node]:
    return [
        function
        for declaration in map(unwrapped, parsed.root.named_children)
        for function in declaration_functions(declaration)
    ]


def rebound_names(nodes: list[Node]) -> set[str]:
    targets = [node.child_by_field_name(BINDINGS.get(node.type, "")) for node in nodes]
    return {name for target in targets for name in bound_names(target)}


def declaration_names(node: Node) -> set[str]:
    target = node.child_by_field_name(DECLARATIONS.get(node.type, ""))
    if node.type == "import_specifier" and target is None:
        target = node.child_by_field_name("name")
    if node.type in {"import_clause", "namespace_import"}:
        return {node_text(child) or "" for child in node.named_children if child.type == "identifier"}
    if target is not None and target.type == "type_identifier":
        return {node_text(target) or ""}
    return bound_names(target)


def mutation(node: Node, parameters: dict[str, str]) -> str | None:
    target = node.child_by_field_name(WRITES.get(node.type, ""))
    if node.type == "unary_expression" and node_text(node.child_by_field_name("operator")) == "delete":
        target = node.child_by_field_name("argument")
    if target is not None and target.type in {"member_expression", "subscript_expression"}:
        receiver = target.child_by_field_name("object")
        name = node_text(receiver) if receiver is not None and receiver.type == "identifier" else None
        return name if parameters.get(name or "") in {"array", "object"} else None
    callee = node.child_by_field_name("function") if node.type == "call_expression" else None
    if callee is None or callee.type != "member_expression":
        return None
    receiver = callee.child_by_field_name("object")
    name = node_text(receiver) if receiver is not None and receiver.type == "identifier" else None
    method = node_text(callee.child_by_field_name("property"))
    return name if method in MUTATORS.get(parameters.get(name or "", ""), frozenset()) else None


def callback_use(parsed: ParsedFile, function: Node, name: str) -> bool:
    declaration = function.child_by_field_name("name")
    if function.parent is not None and function.parent.type == "variable_declarator":
        declaration = function.parent.child_by_field_name("name")
    for node in all_nodes(parsed):
        if (
            node == declaration
            or node.type not in {"identifier", "shorthand_property_identifier"}
            or node_text(node) != name
        ):
            continue
        parent = node.parent
        if parent is None or parent.type != "call_expression" or parent.child_by_field_name("function") != node:
            return True
    return False


def function_findings(parsed: ParsedFile, function: Node, shadowed: set[str]) -> list[Finding]:
    name = function_name(function)
    if name.startswith(("_", "test")) or callback_use(parsed, function, name):
        return []
    nodes = list(own_nodes(function, SCOPES))
    rebound = rebound_names(nodes)
    parameters = {key: kind for key, kind in typed_parameters(function, shadowed).items() if key not in rebound}
    first = {}
    for node in nodes:
        parameter = mutation(node, parameters)
        if parameter is not None:
            first.setdefault(parameter, node)
    return [
        Finding(
            parsed.path, line_of(node), CHECK_ID, Severity.WARNING, MESSAGE.format(function=name, parameter=parameter)
        )
        for parameter, node in first.items()
    ]


def check_parameter_mutation(parsed: ParsedFile) -> list[Finding]:
    if parsed.language not in {"typescript", "tsx"} or is_test_path(PurePath(parsed.path)):
        return []
    shadowed = {name for node in all_nodes(parsed) for name in declaration_names(node) if name in COLLECTION_TYPES}
    return [
        finding for function in module_functions(parsed) for finding in function_findings(parsed, function, shadowed)
    ]
