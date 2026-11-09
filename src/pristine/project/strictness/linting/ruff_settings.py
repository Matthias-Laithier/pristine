import posixpath
import tomllib

from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import array, table
from pristine.project.repository.tools import TOOLS_BY_NAME
from pristine.project.strictness.strictness import UnverifiedConfigError

UNIVERSAL_PER_FILE_PATTERNS = ("*", "**", "**/*.py")
LINT_SELECTORS = frozenset({"select", "extend-select", "ignore", "extend-ignore"})
PER_FILE_MASKS = frozenset({"per-file-ignores", "extend-per-file-ignores"})


def config_path(project: Project) -> str:
    return next(
        (name for name in (*TOOLS_BY_NAME["ruff"].config_files, "pyproject.toml") if name in project.entries),
        "pyproject.toml",
    )


def lint_settings(project: Project, path: str, visited: frozenset[str]) -> dict[str, object]:
    if path in visited:
        raise UnverifiedConfigError(path, f"the extend chain of {path} is circular")
    text = project.reader.text(path)
    if text is None:
        raise UnverifiedConfigError(path, f"{path} is unreadable")
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise UnverifiedConfigError(path, f"{path} is not valid TOML ({error})") from error
    settings = unwrap_settings(path, document)
    if "lint" in settings and not isinstance(settings["lint"], dict):
        raise UnverifiedConfigError(path, f"the lint setting of {path} is not a table")
    validate_consumed_settings(path, settings)
    extended = settings.get("extend")
    if extended is not None and not isinstance(extended, str):
        raise UnverifiedConfigError(path, f"the extend setting of {path} is not a path")
    if extended is None:
        return settings
    target = posixpath.normpath(posixpath.join(posixpath.dirname(path), extended))
    if not project.reader.is_local_file(target):
        raise UnverifiedConfigError(path, f"{path} refers to {extended}, which is not a file of the repository")
    return merged_settings(lint_settings(project, target, visited | {path}), settings)


def unwrap_settings(path: str, document: dict[str, object]) -> dict[str, object]:
    if posixpath.basename(path) != "pyproject.toml":
        return document
    tools = document.get("tool", {})
    if not isinstance(tools, dict):
        raise UnverifiedConfigError(path, "the pyproject tool setting must be a table")
    ruff = tools.get("ruff", {})
    if not isinstance(ruff, dict):
        raise UnverifiedConfigError(path, "the pyproject tool.ruff setting must be a table")
    return dict[str, object](ruff)


def validate_consumed_settings(path: str, settings: dict[str, object]) -> None:
    if (LINT_SELECTORS | PER_FILE_MASKS) & settings.keys():
        raise UnverifiedConfigError(path, "move deprecated top-level Ruff lint selectors and masks into the lint table")
    for name in ("fix", "fix-only"):
        if name in settings and not isinstance(settings[name], bool):
            raise UnverifiedConfigError(path, f"Ruff {name} must be a boolean before command overrides")
    lint = table(settings, "lint")
    for name in sorted(LINT_SELECTORS):
        if name in lint and not string_array(lint[name]):
            raise UnverifiedConfigError(path, f"Ruff lint.{name} must be a list of rule selectors")
    for name in sorted(PER_FILE_MASKS):
        value = lint.get(name, {})
        valid = isinstance(value, dict) and all(string_array(rules) for rules in value.values())
        if not valid:
            raise UnverifiedConfigError(path, f"Ruff lint.{name} must map file patterns to lists of rule selectors")


def string_array(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def merged_settings(base: dict[str, object], settings: dict[str, object]) -> dict[str, object]:
    if "lint" not in settings:
        return {**base, **settings}
    child, parent = table(settings, "lint"), table(base, "lint")
    reset_by_child_select = ("ignore", "extend-select", "extend-ignore")
    inherited = (
        dict(parent)
        if "select" not in child
        else {key: value for key, value in parent.items() if key not in reset_by_child_select}
    )
    lint = {**inherited, **child}
    lint["extend-select"] = [*array(inherited, "extend-select"), *array(child, "extend-select")]
    lint["extend-ignore"] = [*array(inherited, "extend-ignore"), *array(child, "extend-ignore")]
    lint["extend-per-file-ignores"] = accumulated_per_file_ignores(
        table(parent, "extend-per-file-ignores"), table(child, "extend-per-file-ignores")
    )
    return {**base, **settings, "lint": lint}


def accumulated_per_file_ignores(parent: dict[str, object], child: dict[str, object]) -> dict[str, object]:
    accumulated = dict(parent)
    for pattern, rules in child.items():
        inherited = accumulated.get(pattern)
        accumulated[pattern] = (
            [*inherited, *rules] if isinstance(inherited, list) and isinstance(rules, list) else rules
        )
    return accumulated


def selected_rules(settings: dict[str, object]) -> list[object]:
    lint = table(settings, "lint")
    return [*array(lint, "select"), *array(lint, "extend-select")]


def universal_per_file_rules(lint: dict[str, object]) -> set[str]:
    mappings = (table(lint, "per-file-ignores"), table(lint, "extend-per-file-ignores"))
    return {
        rule
        for mapping in mappings
        for pattern, rules in mapping.items()
        if pattern in UNIVERSAL_PER_FILE_PATTERNS and isinstance(rules, list)
        for rule in rules
        if isinstance(rule, str)
    }
