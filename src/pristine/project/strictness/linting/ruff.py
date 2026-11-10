import posixpath
import tomllib

from pristine.project.automation import RULE_ID, is_configured
from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import array, table
from pristine.project.repository.tools import TOOLS_BY_NAME
from pristine.project.strictness.strictness import UnverifiedConfigError
from pristine.reports.findings import Finding, FindingKind, Severity

RUFF = TOOLS_BY_NAME["ruff"]
REQUIRED_RULES = ("S", "ASYNC", "DTZ", "G", "T20", "FBT", "BLE", "ARG", "ERA")
ALL_RULES = "ALL"
FIRST_LINE = 1
RUFF_FIX = 'select or extend-select the S, ASYNC, DTZ, G, T20, FBT, BLE, ARG, and ERA rule sets (or "ALL")'
UNIVERSAL_PER_FILE_PATTERNS = ("*", "**", "**/*.py")


def config_path(project: Project) -> str:
    for name in (*RUFF.config_files, "pyproject.toml"):
        if name in project.entries:
            return name
    return "pyproject.toml"


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
    base = lint_settings(project, target, visited | {path})
    return merged_settings(base, settings)


def merged_settings(base: dict[str, object], settings: dict[str, object]) -> dict[str, object]:
    if "lint" not in settings:
        return base
    child = table(settings, "lint")
    parent = table(base, "lint")
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
        if isinstance(inherited, list) and isinstance(rules, list):
            accumulated[pattern] = [*inherited, *rules]
        else:
            accumulated[pattern] = rules
    return accumulated


def selected_rules(settings: dict[str, object]) -> list[object]:
    lint = table(settings, "lint")
    return [*array(lint, "select"), *array(lint, "extend-select")]


def missing_rules(settings: dict[str, object]) -> list[str]:
    selected = {rule for rule in selected_rules(settings) if isinstance(rule, str)}
    lint = table(settings, "lint")
    ignored = {rule for rule in [*array(lint, "ignore"), *array(lint, "extend-ignore")] if isinstance(rule, str)}
    ignored.update(universal_per_file_rules(lint))
    if ALL_RULES in selected:
        selected = set() if ALL_RULES in ignored else set(REQUIRED_RULES)
    return [rule for rule in REQUIRED_RULES if rule not in selected or rule in ignored]


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


def ruff_configured(project: Project) -> bool:
    manifest = project.root_manifest(RUFF.ecosystem)
    if manifest is None:
        return False
    return is_configured(RUFF, [manifest], project.entries)


def ruff_shortfall(project: Project) -> list[Finding]:
    if not ruff_configured(project):
        return []
    try:
        settings = lint_settings(project, config_path(project), frozenset())
        missing = missing_rules(settings)
    except UnverifiedConfigError as error:
        return [
            Finding(
                project.shown(error.path),
                FIRST_LINE,
                RULE_ID,
                Severity.WARNING,
                f"cannot verify that the Ruff rule sets are configured: {error.reason}",
                FindingKind.VERIFICATION,
            )
        ]
    if not missing:
        return []
    return [
        Finding(
            project.shown(config_path(project)),
            FIRST_LINE,
            RULE_ID,
            Severity.ERROR,
            f"Ruff does not enable the required rule sets ({', '.join(missing)}); {RUFF_FIX}",
        )
    ]
