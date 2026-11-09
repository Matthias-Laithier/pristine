import posixpath
import tomllib

from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import array, table
from pristine.project.repository.tools import TOOLS_BY_NAME
from pristine.project.strictness.strictness import UnverifiedConfigError

UNIVERSAL_PER_FILE_PATTERNS = ("*", "**", "**/*.py")


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
    settings = table(table(document, "tool"), "ruff") if path == "pyproject.toml" else dict[str, object](document)
    extended = settings.get("extend")
    if extended is not None and not isinstance(extended, str):
        raise UnverifiedConfigError(path, f"the extend setting of {path} is not a path")
    if extended is None:
        return settings
    target = posixpath.normpath(posixpath.join(posixpath.dirname(path), extended))
    if not project.reader.is_local_file(target):
        raise UnverifiedConfigError(path, f"{path} refers to {extended}, which is not a file of the repository")
    return merged_settings(lint_settings(project, target, visited | {path}), settings)


def merged_settings(base: dict[str, object], settings: dict[str, object]) -> dict[str, object]:
    if "lint" not in settings:
        return base
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
