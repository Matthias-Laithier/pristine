import re
from collections.abc import Iterator
from dataclasses import dataclass, field

lazy from tree_sitter import Node

from pristine.checks.core.placement.global_placement.type_expressions import is_type_expression
from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding, Severity
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.nodes import ANONYMOUS_FUNCTION_KINDS, CALL_KINDS
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, module_statements, node_text
from pristine.syntax.python_calls import import_bindings

RULE_ID = "CR-6"
PYTHON = "python"
BINDING_LIST_KINDS = frozenset({"var_spec_list", "const_spec_list"})
VALUE_LIST_KINDS = frozenset({"expression_list"})
REFERENCE_FIELDS = ("value", "right", "type")
NAME_FIELDS = ("name", "left")
TYPE_ALIAS_ANNOTATION = "TypeAlias"
IMPORT_CALL_PREFIXES = ("require(", "import(", "await import(")
BLANK_NAME = re.compile(r"_")
SPECIAL_NAME = re.compile(r"_|__\w*")
MESSAGE = "global '{names}' sits below a function or class; move it to the top of the file, right after the imports"
MUTATION_TARGET_KINDS = frozenset({"attribute", "subscript", "member_expression", "subscript_expression"})
RUST_STARTS = ("function_item", "impl_item", "struct_item", "enum_item", "trait_item")


@dataclass(frozen=True)
class LanguageSpec:
    binding_kinds: tuple[str, ...]
    start_kinds: tuple[str, ...]
    exempt_name: re.Pattern[str] = SPECIAL_NAME


@dataclass
class ModuleState:
    imports: dict[str, str]
    started: bool = False
    known_names: set[str] = field(default_factory=set)


SCRIPT_SPEC = LanguageSpec(
    ("variable_declarator",), ("function_declaration", "generator_function_declaration", "class_declaration")
)
LANGUAGE_SPECS = dict.fromkeys(SCRIPT_LANGUAGES, SCRIPT_SPEC) | {
    PYTHON: LanguageSpec(("assignment",), ("function_definition", "class_definition")),
    "go": LanguageSpec(("var_spec", "const_spec"), ("function_declaration", "method_declaration"), BLANK_NAME),
    "rust": LanguageSpec(("const_item", "static_item"), RUST_STARTS, BLANK_NAME),
}


def bindings(node: Node, spec: LanguageSpec) -> list[Node]:
    if node.type in spec.binding_kinds:
        return [node]
    children = [child for child in node.named_children if child.type in BINDING_LIST_KINDS] or [node]
    return [binding for child in children for binding in child.named_children if binding.type in spec.binding_kinds]


def identifiers(node: Node) -> set[str]:
    return {node_text(child) or "" for child in all_nodes(node) if "identifier" in child.type}


def field_identifiers(node: Node, field_name: str) -> set[str]:
    return {name for child in node.children_by_field_name(field_name) for name in identifiers(child)}


def bound_names(binding: Node) -> set[str]:
    targets = [target for field_name in NAME_FIELDS for target in binding.children_by_field_name(field_name)]
    if any(target.type in MUTATION_TARGET_KINDS for target in targets):
        return set()
    return {name for target in targets for name in identifiers(target)}


def value_of(binding: Node) -> Node | None:
    value = binding.child_by_field_name("value") or binding.child_by_field_name("right")
    if value is not None and value.type in VALUE_LIST_KINDS and value.named_child_count == 1:
        return value.named_children[0]
    return value


def is_function_valued(value: Node | None) -> bool:
    arguments = value.child_by_field_name("arguments") if value is not None and value.type in CALL_KINDS else None
    candidates = [value, *([] if arguments is None else arguments.named_children)]
    return any(candidate is not None and candidate.type in ANONYMOUS_FUNCTION_KINDS for candidate in candidates)


def is_exempt(binding: Node, names: set[str], spec: LanguageSpec, imports: dict[str, str]) -> bool:
    is_alias = (node_text(binding.child_by_field_name("type")) or "").endswith(TYPE_ALIAS_ANNOTATION)
    is_type = binding.child_by_field_name("type") is None and is_type_expression(value_of(binding), imports)
    is_import = (node_text(value_of(binding)) or "").startswith(IMPORT_CALL_PREFIXES)
    return is_alias or is_type or is_import or all(spec.exempt_name.fullmatch(name) for name in names)


def reads_known_name(binding: Node, state: ModuleState) -> bool:
    referenced = {name for field_name in REFERENCE_FIELDS for name in field_identifiers(binding, field_name)}
    return bool(referenced & state.known_names)


def misplaced_bindings(item: Node, spec: LanguageSpec, state: ModuleState) -> Iterator[tuple[Node, set[str]]]:
    for binding in bindings(item, spec):
        names = bound_names(binding)
        is_definition = is_function_valued(value_of(binding))
        is_exempt_binding = is_definition or not names or is_exempt(binding, names, spec, state.imports)
        if state.started and not is_exempt_binding and not reads_known_name(binding, state):
            yield binding, names
            continue
        state.started = state.started or is_definition
        if state.started:
            state.known_names |= names


def record_definition(item: Node, spec: LanguageSpec, state: ModuleState) -> None:
    if bindings(item, spec):
        return
    state.started = state.started or item.type in spec.start_kinds
    if state.started:
        state.known_names |= {name for holder in [item, *item.named_children] for name in bound_names(holder)}


def check_global_placement(parsed: ParsedFile) -> list[Finding]:
    spec = LANGUAGE_SPECS.get(parsed.language)
    if spec is None:
        return []
    state = ModuleState(import_bindings(parsed) if parsed.language == PYTHON else {})
    findings = []
    for item in module_statements(parsed.root):
        record_definition(item, spec, state)
        for binding, names in misplaced_bindings(item, spec, state):
            message = MESSAGE.format(names=", ".join(sorted(names)))
            findings.append(Finding(parsed.path, line_of(binding), RULE_ID, Severity.WARNING, message))
    return findings


CHECK = FileCheck(
    rule_id=RULE_ID,
    summary=(
        "Module-level variables and constants defined below the first function or class. A value that reads "
        "an earlier definition, __all__, and type aliases (TypeAlias annotations, typing generics, unions, "
        "TypeVar, NewType, TypedDict and pydantic create_model calls) are allowed."
    ),
    run=check_global_placement,
)
