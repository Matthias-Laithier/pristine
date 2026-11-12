import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from functools import cached_property, partial

lazy from tree_sitter import Node

from pristine.checks.core.placement.global_placement.references import bound_names, identifiers, module_references
from pristine.checks.core.placement.global_placement.script_references import references as script_references
from pristine.checks.core.placement.global_placement.type_expressions import is_type_expression
from pristine.checks.definitions import FileCheck
from pristine.reports.findings import Finding, Severity
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.nodes import ANONYMOUS_FUNCTION_KINDS, CALL_KINDS
from pristine.syntax.parsing import ParsedFile, line_of, module_statements, node_text
from pristine.syntax.python_calls import import_bindings

CHECK_ID = "STR-5"
PYTHON = "python"
VALUE_LIST_KINDS = frozenset({"expression_list"})
REFERENCE_FIELDS = ("value", "right", "type")
TYPE_ALIAS_ANNOTATION = "TypeAlias"
IMPORT_CALL_PREFIXES = ("require(", "import(", "await import(")
SPECIAL_NAME = re.compile(r"_|__\w*")
MESSAGE = "global '{names}' sits below a function or class; move it to the top of the file, right after the imports"


@dataclass(frozen=True)
class LanguageSpec:
    binding_kinds: tuple[str, ...]
    start_kinds: tuple[str, ...]
    exempt_name: re.Pattern[str] = SPECIAL_NAME


SCRIPT_SPEC = LanguageSpec(
    ("variable_declarator",), ("function_declaration", "generator_function_declaration", "class_declaration")
)
LANGUAGE_SPECS = dict.fromkeys(SCRIPT_LANGUAGES, SCRIPT_SPEC) | {
    PYTHON: LanguageSpec(("assignment",), ("function_definition", "class_definition")),
}


@dataclass
class Declaration:
    names: set[str]
    read_references: Callable[[], set[str]]

    @cached_property
    def references(self) -> set[str]:
        return self.read_references() - self.names


@dataclass
class ModuleState:
    imports: dict[str, str]
    started: bool = False
    declarations: list[Declaration] = field(default_factory=list)


def bindings(node: Node, spec: LanguageSpec) -> list[Node]:
    if node.type in spec.binding_kinds:
        return [node]
    return [binding for binding in node.named_children if binding.type in spec.binding_kinds]


def field_identifiers(node: Node, field_name: str) -> set[str]:
    return {name for child in node.children_by_field_name(field_name) for name in identifiers(child)}


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


def reads_adjacent_dependencies(binding: Node, state: ModuleState) -> bool:
    referenced = {name for field_name in REFERENCE_FIELDS for name in field_identifiers(binding, field_name)}
    known_names = {name for declaration in state.declarations for name in declaration.names}
    dependencies = referenced & known_names
    if not dependencies:
        return False
    related = dependencies | bound_names(binding)
    while True:
        expanded = related | {
            name
            for declaration in state.declarations
            if related & declaration.names or related & declaration.references
            for name in declaration.names | (declaration.references & known_names)
        }
        if expanded == related:
            break
        related = expanded
    for declaration in reversed(state.declarations):
        if not related & declaration.names:
            return False
        dependencies -= declaration.names
        if not dependencies:
            return True
    return False


def misplaced_bindings(item: Node, spec: LanguageSpec, state: ModuleState) -> Iterator[tuple[Node, set[str]]]:
    for binding in bindings(item, spec):
        names = bound_names(binding)
        is_definition = is_function_valued(value_of(binding))
        is_candidate = state.started and not is_definition and bool(names)
        if (
            is_candidate
            and not is_exempt(binding, names, spec, state.imports)
            and not reads_adjacent_dependencies(binding, state)
        ):
            yield binding, names
        state.started = state.started or is_definition
        if state.started and names:
            state.declarations.append(Declaration(names, partial(identifiers, binding)))


def record_definition(item: Node, spec: LanguageSpec, state: ModuleState) -> None:
    state.started = state.started or item.type in spec.start_kinds
    if state.started and not bindings(item, spec):
        names = {name for holder in [item, *item.named_children] for name in bound_names(holder)}
        if names:
            read_references = script_references if spec is SCRIPT_SPEC else module_references
            state.declarations.append(Declaration(names, partial(read_references, item)))


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
            findings.append(Finding(parsed.path, line_of(binding), CHECK_ID, Severity.WARNING, message))
    return findings


CHECK = FileCheck(
    check_id=CHECK_ID,
    title="Global Placement",
    summary=(
        "Module-level variables and constants defined below the first function or class. Values immediately beside "
        "their dependencies, __all__, and type aliases (TypeAlias annotations, typing generics, unions, "
        "TypeVar, NewType, TypedDict and pydantic create_model calls) are allowed."
    ),
    run=check_global_placement,
)
