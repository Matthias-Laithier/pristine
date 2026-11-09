from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import array, table
from pristine.project.strictness.annotations.options import (
    UNIVERSAL_PATTERNS,
    code_overrides,
    codes,
    has_option,
    option_values,
)
from pristine.project.strictness.annotations.scope import excluded_python_sources, verify_source_scope
from pristine.project.strictness.linting.ruff import config_path, lint_settings
from pristine.project.strictness.strictness import UnverifiedConfigError

ANNOTATION_RULES = ("ANN001", "ANN002", "ANN003", "ANN201", "ANN202", "ANN204", "ANN205", "ANN206")
SUPPRESSIONS = ("ignore-fully-untyped", "suppress-dummy-args", "suppress-none-returning", "mypy-init-return")
NON_GATING = frozenset(
    {
        "--exit-zero",
        "-e",
        "--fix-only",
        "--diff",
        "--show-settings",
        "--show-files",
        "--add-noqa",
        "--add-ignore",
        "--help",
        "-h",
    }
)
UNSUPPORTED = frozenset({"--config", "--per-file-ignores", "--extend-per-file-ignores", "--extension"})
EXCLUDES = frozenset({"--exclude", "--extend-exclude"})
SELECTION_OPTIONS = ("select", "extend-select", "ignore", "extend-ignore")
LEGACY_LINT_KEYS = frozenset((*SELECTION_OPTIONS, "per-file-ignores", "extend-per-file-ignores", "flake8-annotations"))


def specificity(rule: str, selectors: list[str]) -> int:
    return max(
        (
            0 if selector == "ALL" else len(selector)
            for selector in selectors
            if rule.startswith(selector) or selector == "ALL"
        ),
        default=-1,
    )


def enabled(rule: str, selected: list[str], ignored: list[str]) -> bool:
    return specificity(rule, selected) > specificity(rule, ignored)


def effective_settings(project: Project, arguments: list[str]) -> tuple[str, dict[str, object]]:
    path = config_path(project)
    settings = {} if "--isolated" in arguments else lint_settings(project, path, frozenset())
    if LEGACY_LINT_KEYS.intersection(settings):
        raise UnverifiedConfigError(path, "legacy top-level Ruff lint settings need review")
    lint = table(settings, "lint")
    if option_values(arguments, "--select"):
        lint = {
            key: value
            for key, value in lint.items()
            if key not in {"select", "extend-select", "ignore", "extend-ignore"}
        }
    overrides = code_overrides(arguments, SELECTION_OPTIONS)
    for name in ("extend-select", "extend-ignore"):
        if name in overrides:
            overrides[name] = codes(lint.get(name)) + codes(overrides[name])
    lint.update(overrides)
    return path, {**settings, "lint": lint}


def per_file_shortfall(lint: dict[str, object], path: str) -> str | None:
    mappings = (table(lint, "per-file-ignores"), table(lint, "extend-per-file-ignores"))
    ignored_by_pattern = [(pattern, codes(ignored)) for mapping in mappings for pattern, ignored in mapping.items()]
    patterns = [
        pattern
        for pattern, ignored in ignored_by_pattern
        if any(specificity(rule, ignored) >= 0 for rule in ANNOTATION_RULES)
    ]
    for pattern in patterns:
        if pattern in UNIVERSAL_PATTERNS:
            return "Ruff ignores annotation rules for every Python file"
        raise UnverifiedConfigError(path, f"Ruff excludes annotation rules for {pattern}")
    return None


def scoped_settings(project: Project, path: str, settings: dict[str, object], arguments: list[str]) -> None:
    if has_option(arguments, UNSUPPORTED):
        raise UnverifiedConfigError("Makefile", "Ruff configuration overrides are not statically supported")
    if has_option(arguments, EXCLUDES) or array(settings, "exclude") or array(settings, "extend-exclude"):
        raise UnverifiedConfigError(path, "Ruff file exclusions need review")
    if array(table(settings, "lint"), "exclude"):
        raise UnverifiedConfigError(path, "Ruff lint exclusions need review")
    nested = [
        name
        for name in project.files
        if "/" in name and name.rsplit("/", 1)[-1] in {"ruff.toml", ".ruff.toml", "pyproject.toml"}
    ]
    if nested and "--isolated" not in arguments:
        raise UnverifiedConfigError(path, "nested Python configuration needs review: " + ", ".join(nested))


def ruff_annotations(project: Project, arguments: list[str]) -> str | None:
    if has_option(arguments, NON_GATING):
        return "Ruff is invoked without enforcing its findings"
    path, settings = effective_settings(project, arguments)
    scoped_settings(project, path, settings, arguments)
    verify_source_scope(project, arguments, ruff=True)
    verify_gitignore_scope(project, arguments, settings)
    lint = table(settings, "lint")
    selected = codes(lint.get("select")) + codes(lint.get("extend-select"))
    ignored = codes(lint.get("ignore")) + codes(lint.get("extend-ignore"))
    missing = [rule for rule in ANNOTATION_RULES if not enabled(rule, selected, ignored)]
    if missing:
        return "Ruff does not enforce " + ", ".join(missing)
    suppressions = table(lint, "flake8-annotations")
    disabled = [name for name in SUPPRESSIONS if suppressions.get(name) is True]
    if disabled:
        return "Ruff suppresses annotations with " + ", ".join(disabled)
    return per_file_shortfall(lint, path)


def verify_gitignore_scope(project: Project, arguments: list[str], settings: dict[str, object]) -> None:
    if "--no-respect-gitignore" in arguments or settings.get("respect-gitignore") is False:
        return
    sources = [path for path in project.files if path.endswith((".py", ".pyi"))]
    ignores = [path for path in project.files if path.rsplit("/", 1)[-1] == ".gitignore"]
    for path in ignores:
        text = project.reader.text(path)
        if text is None:
            raise UnverifiedConfigError(path, "Git ignore rules are unreadable")
        parent = path.rpartition("/")[0]
        prefix = parent + "/" if parent else ""
        relative = [source.removeprefix(prefix) for source in sources if source.startswith(prefix)]
        patterns = [
            line.strip().strip("/") for line in text.splitlines() if line.strip() and not line.startswith(("#", "!"))
        ]
        if excluded_python_sources(relative, patterns):
            raise UnverifiedConfigError(path, "Git ignore rules may exclude discovered Python source from Ruff")
