import re
from collections.abc import Iterator
from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.checks.boundaries.data_flow.scattered_settings.composition_roots import is_composition_root, is_within
from pristine.checks.boundaries.data_flow.scattered_settings.scripts import (
    environment_reads as script_environment_reads,
)
from pristine.checks.definitions import FileCheck
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.syntax.calls import callee_of
from pristine.syntax.nodes import FUNCTION_KINDS
from pristine.syntax.parsing import ParsedFile, function_name, line_of, module_statements, node_text
from pristine.syntax.python_calls import import_bindings, qualified_callee
from pristine.syntax.python_strings import is_constant_string

CHECK_ID = "SAFE-1"
PYTEST_HOOK_PREFIX = "pytest_"
SETTINGS_BASES = ("pydantic_settings", "pydantic.BaseSettings", "pydantic.v1.BaseSettings")
ENVIRONMENT = "os.environ"
ENVIRONMENT_CALLS = frozenset({"os.environ.get", "os.getenv"})
WRITE_TARGETS = {"assignment": "left", "augmented_assignment": "left"}
DELETE_KIND = "delete_statement"
VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
PROCESS_VARIABLES = re.compile(
    r"PATH|HOME|USER(NAME|PROFILE)?|SHELL|TERM|EDITOR|VISUAL|PAGER|TE?MP(DIR)?|PWD|LANG|LC_\w+|XDG_\w+|DISPLAY"
    r"|COLUMNS|LINES|NO_COLOR|FORCE_COLOR|CI|VIRTUAL_ENV|PYTHON\w*|SSH_\w+|(LOCAL)?APPDATA|SYSTEMROOT|COMSPEC"
    r"|HOSTNAME|KUBERNETES_\w+|PROGRAMFILES(\(X86\)|W6432)?|WINDIR|SSL_CERT_(FILE|DIR)|(HTTPS?|NO|ALL)_PROXY"
    r"|BUILDKITE(_\w+)?|GITHUB_(ACTIONS|REF|REF_NAME|SHA|RUN_\w+|WORKSPACE|EVENT_\w+|OUTPUT|STEP_SUMMARY)"
)


def is_settings_base(base: str, bindings: dict[str, str]) -> bool:
    return is_within(qualified_callee(base, bindings), SETTINGS_BASES)


def class_bases(node: Node) -> list[str]:
    bases = node.child_by_field_name("superclasses")
    return [] if bases is None else [node_text(base) or "" for base in bases.named_children]


def defines_settings_class(parsed: ParsedFile, bindings: dict[str, str]) -> bool:
    classes = {
        node_text(node.child_by_field_name("name")) or "": class_bases(node)
        for node in parsed.nodes_of("class_definition")
    }
    settings = {name for name, bases in classes.items() if any(is_settings_base(base, bindings) for base in bases)}
    pending = classes.keys() - settings
    while subclasses := {name for name in pending if not settings.isdisjoint(classes[name])}:
        settings |= subclasses
        pending -= subclasses
    return bool(settings)


def is_exempt(parsed: ParsedFile, bindings: dict[str, str]) -> bool:
    is_settings_module = defines_settings_class(parsed, bindings)
    return is_test_path(PurePath(parsed.path)) or is_settings_module or is_composition_root(parsed, bindings)


def is_written(subscript: Node) -> bool:
    parent = subscript.parent
    if parent is None:
        return False
    target = parent.child_by_field_name(WRITE_TARGETS.get(parent.type, ""))
    return target == subscript or parent.type == DELETE_KIND


def read_key(node: Node, bindings: dict[str, str]) -> Node | None:
    if node.type == "call" and qualified_callee(callee_of(node), bindings) in ENVIRONMENT_CALLS:
        arguments = node.child_by_field_name("arguments")
        return None if arguments is None or not arguments.named_children else arguments.named_children[0]
    subject = node_text(node.child_by_field_name("value")) or ""
    is_environment = node.type == "subscript" and qualified_callee(subject, bindings) == ENVIRONMENT
    return node.child_by_field_name("subscript") if is_environment and not is_written(node) else None


def module_strings(root: Node) -> dict[str, Node]:
    assignments = (statement for statement in module_statements(root) if statement.type == "assignment")
    pairs = ((node_text(node.child_by_field_name("left")), node.child_by_field_name("right")) for node in assignments)
    return {
        name: value for name, value in pairs if name is not None and value is not None and is_constant_string(value)
    }


def is_setting_name(key: Node | None, constants: dict[str, Node]) -> bool:
    literal = constants.get(node_text(key) or "") if key is not None and key.type == "identifier" else key
    if literal is None or not is_constant_string(literal):
        return False
    name = (node_text(literal) or "").strip("'\"")
    return VARIABLE_NAME.fullmatch(name) is not None and PROCESS_VARIABLES.fullmatch(name) is None


def is_inside_application_function(node: Node) -> bool:
    scope = node.parent
    while scope is not None and scope.type not in FUNCTION_KINDS:
        scope = scope.parent
    return scope is not None and not function_name(scope).startswith(PYTEST_HOOK_PREFIX)


def environment_reads(parsed: ParsedFile, bindings: dict[str, str]) -> Iterator[Node]:
    constants = module_strings(parsed.root)
    for node in parsed.nodes_of("call", "subscript"):
        key = read_key(node, bindings)
        if is_setting_name(key, constants) and is_inside_application_function(node):
            yield node


def check_scattered_settings(parsed: ParsedFile) -> list[Finding]:
    if parsed.language in {"javascript", "typescript", "tsx"}:
        message = (
            "environment read inside a function; validate settings once at startup and pass the typed settings value in"
        )
        lines = sorted(
            {
                line_of(node)
                for node, key in script_environment_reads(parsed)
                if VARIABLE_NAME.fullmatch(key) and PROCESS_VARIABLES.fullmatch(key) is None
            }
        )
        return [Finding(parsed.path, line, CHECK_ID, Severity.WARNING, message) for line in lines]
    if parsed.language != "python":
        return []
    bindings = import_bindings(parsed)
    if is_exempt(parsed, bindings):
        return []
    message = (
        "environment read inside a function; validate settings once at startup and pass the typed settings value in"
    )
    lines = sorted({line_of(node) for node in environment_reads(parsed, bindings)})
    return [Finding(parsed.path, line, CHECK_ID, Severity.WARNING, message) for line in lines]


CHECK = FileCheck(
    check_id=CHECK_ID,
    title="Scattered Settings Reads",
    summary=(
        "Python reads of a named setting (os.environ[...], os.environ.get, os.getenv) inside functions, keyed by "
        "a string literal or a same-module string constant. Modules defining a pydantic-settings BaseSettings "
        "subclass, tests, pytest hooks, process variables such as PATH or HOME, and composition roots are exempt: "
        "modules with a __main__ guard or a shebang, __main__.py and the modules it imports, the modules that "
        "pyproject.toml scripts name, and modules defining invoke or nox tasks."
        " JS/TS literal process.env property/index reads in functions; tests, shebangs, named startup/config "
        "modules and functions, process variables, NODE_ENV/NODE_OPTIONS and framework public-env prefixes are exempt."
    ),
    run=check_scattered_settings,
)
