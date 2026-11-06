import re
from collections.abc import Iterator
from pathlib import PurePath

from tree_sitter import Node

from pristine.checks.registry import FileCheck, register_file_check
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.syntax.calls import callee_of
from pristine.syntax.parsing import ParsedFile, all_nodes, function_name, line_of, node_text
from pristine.syntax.python_calls import import_bindings, qualified_callee
from pristine.syntax.syntax_kinds import FUNCTION_KINDS

RULE_ID = "BS-1"
SHEBANG = "#!"
SCRIPT_DIRECTORIES = frozenset({"scripts", "bin", "examples"})
COMPOSITION_ROOTS = frozenset({"main.py", "__main__.py", "app.py", "cli.py", "manage.py", "conftest.py"})
TASK_RUNNERS = frozenset({"setup.py", "noxfile.py", "tasks.py"})
SETTINGS_MODULES = frozenset({"settings.py", "config.py", "configuration.py"})
PYTEST_HOOK_PREFIX = "pytest_"
ENVIRONMENT = "os.environ"
ENVIRONMENT_CALLS = frozenset({"os.environ.get", "os.getenv"})
SETTINGS_SUFFIX = "Settings"
WRITE_TARGETS = {"assignment": "left", "augmented_assignment": "left"}
DELETE_KIND = "delete_statement"
STARTUP_FUNCTION = "main"
MAIN_GUARD = re.compile(r"^if __name__ == ['\"]__main__['\"]:", re.MULTILINE)
CONSTANT_KEY = re.compile(r"[A-Z][A-Z0-9_]*")
STRING_KEY = re.compile(r"['\"](?P<name>[A-Za-z_][A-Za-z0-9_]*)['\"]")
PROCESS_VARIABLES = re.compile(
    r"PATH|HOME|USER(NAME|PROFILE)?|SHELL|TERM|EDITOR|VISUAL|PAGER|TE?MP(DIR)?|PWD|LANG|LC_\w+|XDG_\w+|DISPLAY"
    r"|COLUMNS|LINES|NO_COLOR|FORCE_COLOR|CI|VIRTUAL_ENV|PYTHON\w*|SSH_\w+|(LOCAL)?APPDATA|SYSTEMROOT|COMSPEC"
    r"|HOSTNAME|KUBERNETES_\w+|PROGRAMFILES(\(X86\)|W6432)?|WINDIR|SSL_CERT_(FILE|DIR)|(HTTPS?|NO|ALL)_PROXY"
    r"|BUILDKITE(_\w+)?|GITHUB_(ACTIONS|REF|REF_NAME|SHA|RUN_\w+|WORKSPACE|EVENT_\w+|OUTPUT|STEP_SUMMARY)"
)


def is_settings_class(node: Node) -> bool:
    bases = node.child_by_field_name("superclasses")
    names = [] if bases is None else [node_text(base) or "" for base in bases.named_children]
    return node.type == "class_definition" and any(name.endswith(SETTINGS_SUFFIX) for name in names)


def is_exempt(parsed: ParsedFile) -> bool:
    path = PurePath(parsed.path)
    is_script = parsed.text.startswith(SHEBANG) or not SCRIPT_DIRECTORIES.isdisjoint(path.parts[:-1])
    is_entrypoint = path.name in COMPOSITION_ROOTS | TASK_RUNNERS or MAIN_GUARD.search(parsed.text) is not None
    is_settings = path.name in SETTINGS_MODULES or any(map(is_settings_class, all_nodes(parsed.root)))
    return is_script or is_entrypoint or is_settings or is_test_path(path)


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


def is_setting_name(key: Node | None) -> bool:
    text = node_text(key) or ""
    literal = STRING_KEY.fullmatch(text)
    if literal is not None:
        return PROCESS_VARIABLES.fullmatch(literal["name"]) is None
    return key is not None and key.type == "identifier" and CONSTANT_KEY.fullmatch(text) is not None


def is_inside_application_function(node: Node) -> bool:
    scope = node.parent
    while scope is not None and scope.type not in FUNCTION_KINDS:
        scope = scope.parent
    name = "" if scope is None else function_name(scope)
    return scope is not None and name != STARTUP_FUNCTION and not name.startswith(PYTEST_HOOK_PREFIX)


def environment_reads(root: Node) -> Iterator[Node]:
    bindings = import_bindings(root)
    for node in all_nodes(root):
        if is_setting_name(read_key(node, bindings)) and is_inside_application_function(node):
            yield node


def check_scattered_settings(parsed: ParsedFile) -> list[Finding]:
    if parsed.language != "python" or is_exempt(parsed):
        return []
    message = (
        "environment read inside a function; parse every setting once at startup into a pydantic-settings "
        "BaseSettings model and pass the settings value in"
    )
    lines = sorted({line_of(node) for node in environment_reads(parsed.root)})
    return [Finding(parsed.path, line, RULE_ID, Severity.WARNING, message) for line in lines]


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Python reads of a named setting (os.environ[...], os.environ.get, os.getenv) inside functions. "
            "BaseSettings and config modules, composition roots, main() and pytest hooks, task runners, tests, "
            "scripts, and process variables such as PATH or HOME are exempt."
        ),
        run=check_scattered_settings,
    )
)
