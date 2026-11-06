from collections.abc import Callable

lazy from tree_sitter import Node

from pristine.registration import registering
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.parsing import ParsedFile, all_nodes, module_statements, node_text
from pristine.syntax.python_calls import import_bindings, qualified_callee

REBINDABLE = "rebindable"
PYTHON_COLLECTION = "python_collection"
PYTHON_LITERALS = frozenset(
    {"list", "dictionary", "set", "list_comprehension", "dictionary_comprehension", "set_comprehension"}
)
PYTHON_BUILTIN_FACTORIES = frozenset({"dict", "list", "set"})
COLLECTIONS_FACTORIES = frozenset(
    {"collections.defaultdict", "collections.Counter", "collections.OrderedDict", "collections.deque"}
)
JS_KINDS = {"array": "array", "object": "object", "Map": "collection", "Set": "collection"}
JS_REBINDABLE_KEYWORDS = frozenset({"let", "var"})
JS_DECLARATION_KINDS = frozenset({"lexical_declaration", "variable_declaration"})

BINDING_PARENTS = frozenset(
    {"parameters", "lambda_parameters", "pattern_list", "tuple_pattern", "list_splat_pattern", "as_pattern_target"}
    | {"dictionary_splat_pattern", "typed_parameter", "formal_parameters", "array_pattern", "object_pattern"}
    | {"pair_pattern", "rest_pattern", "assignment_pattern", "global_statement", "nonlocal_statement"}
)
BINDING_FIELDS = {
    "assignment": "left",
    "for_statement": "left",
    "for_in_clause": "left",
    "named_expression": "name",
    "default_parameter": "name",
    "typed_default_parameter": "name",
    "variable_declarator": "name",
    "for_in_statement": "left",
    "catch_clause": "parameter",
    "required_parameter": "pattern",
    "optional_parameter": "pattern",
    "arrow_function": "parameter",
    "function_declaration": "name",
}
BINDING_KINDS = frozenset({"identifier", "shorthand_property_identifier_pattern"})

type Globals = dict[str, frozenset[str]]
type GlobalsCollector = Callable[[ParsedFile], Globals]
_COLLECTORS: dict[str, GlobalsCollector] = {}


def is_python_collection(value: Node | None, imports: dict[str, str]) -> bool:
    if value is not None and value.type == "call":
        callee = node_text(value.child_by_field_name("function")) or ""
        return callee in PYTHON_BUILTIN_FACTORIES or qualified_callee(callee, imports) in COLLECTIONS_FACTORIES
    return value is not None and value.type in PYTHON_LITERALS


@registering(_COLLECTORS, "python")
def python_globals(parsed: ParsedFile) -> Globals:
    imports = import_bindings(parsed)
    assignments = [statement for statement in module_statements(parsed.root) if statement.type == "assignment"]
    pairs = [
        (statement.child_by_field_name("left"), statement.child_by_field_name("right")) for statement in assignments
    ]
    collections = [left for left, right in pairs if left is not None and is_python_collection(right, imports)]
    return {node_text(left) or "": frozenset({PYTHON_COLLECTION}) for left in collections if left.type == "identifier"}


def js_literal_kind(value: Node | None) -> str | None:
    if value is not None and value.type == "satisfies_expression":
        value = value.named_children[0]
    if value is None:
        return None
    key = node_text(value.child_by_field_name("constructor")) if value.type == "new_expression" else value.type
    return JS_KINDS.get(key or "")


def declared_kinds(keyword: str, declarator: Node) -> tuple[str, frozenset[str]]:
    literal_kind = js_literal_kind(declarator.child_by_field_name("value"))
    rebindable = {REBINDABLE} if keyword in JS_REBINDABLE_KEYWORDS else set[str]()
    literal = set[str]() if literal_kind is None else {literal_kind}
    return node_text(declarator.child_by_field_name("name")) or "", frozenset(rebindable | literal)


def is_named_binding(declarator: Node) -> bool:
    name = declarator.child_by_field_name("name")
    return name is not None and name.type == "identifier"


@registering(_COLLECTORS, *SCRIPT_LANGUAGES)
def js_globals(parsed: ParsedFile) -> Globals:
    declarations = [
        statement for statement in module_statements(parsed.root) if statement.type in JS_DECLARATION_KINDS
    ]
    declared = [
        declared_kinds(node_text(declaration.children[0]) or "", declarator)
        for declaration in declarations
        for declarator in declaration.named_children
        if declarator.type == "variable_declarator" and is_named_binding(declarator)
    ]
    return {name: kinds for name, kinds in declared if kinds}


def module_globals(language: str, parsed: ParsedFile) -> Globals | None:
    collector = _COLLECTORS.get(language)
    return None if collector is None else collector(parsed)


def is_binding(node: Node) -> bool:
    parent = node.parent
    if parent is None or node.type != "identifier":
        return parent is not None
    field = BINDING_FIELDS.get(parent.type)
    return parent.type in BINDING_PARENTS or (field is not None and parent.child_by_field_name(field) == node)


def binds_locally(scope: Node, name: str) -> bool:
    candidates = (node for node in all_nodes(scope) if node.type in BINDING_KINDS)
    return any(node_text(node) == name and is_binding(node) for node in candidates)
