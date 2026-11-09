from pristine.project.repository.manifests import table
from pristine.project.strictness.strictness import UnverifiedConfigError

LINT_SELECTORS = frozenset({"select", "extend-select", "ignore", "extend-ignore"})
PER_FILE_MASKS = frozenset({"per-file-ignores", "extend-per-file-ignores"})
ANNOTATION_SUPPRESSIONS = ("ignore-fully-untyped", "suppress-dummy-args", "suppress-none-returning", "mypy-init-return")


def validate_consumed_settings(path: str, settings: dict[str, object]) -> None:
    if (LINT_SELECTORS | PER_FILE_MASKS) & settings.keys():
        raise UnverifiedConfigError(path, "move deprecated top-level Ruff lint selectors and masks into the lint table")
    for name in ("fix", "fix-only"):
        if name in settings and not isinstance(settings[name], bool):
            raise UnverifiedConfigError(path, f"Ruff {name} must be a boolean before command overrides")
    if "lint" in settings and not isinstance(settings["lint"], dict):
        raise UnverifiedConfigError(path, f"the lint setting of {path} is not a table")
    lint = table(settings, "lint")
    for name in sorted(LINT_SELECTORS):
        if name in lint and not string_array(lint[name]):
            raise UnverifiedConfigError(path, f"Ruff lint.{name} must be a list of rule selectors")
    for name in sorted(PER_FILE_MASKS):
        value = lint.get(name, {})
        valid = isinstance(value, dict) and all(string_array(rules) for rules in value.values())
        if not valid:
            raise UnverifiedConfigError(path, f"Ruff lint.{name} must map file patterns to lists of rule selectors")
    validate_annotation_suppressions(path, lint)


def string_array(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def validate_annotation_suppressions(path: str, lint: dict[str, object]) -> None:
    suppressions = lint.get("flake8-annotations", {})
    if not isinstance(suppressions, dict):
        raise UnverifiedConfigError(path, "Ruff flake8-annotations settings must be a table")
    for name in ANNOTATION_SUPPRESSIONS:
        if name in suppressions and not isinstance(suppressions[name], bool):
            raise UnverifiedConfigError(path, f"Ruff flake8-annotations.{name} must be a boolean before overrides")
