from pristine.project.automation import CHECK_ID, is_configured, is_typescript
from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import array, table
from pristine.project.repository.tools import TOOLS_BY_NAME
from pristine.project.strictness.linting.eslint_configurations import (
    PACKAGE_CONFIG,
    config_path,
    package_config,
    read_config,
    unsupported_config,
)
from pristine.project.strictness.strictness import UnverifiedConfigError
from pristine.reports.findings import Finding, FindingKind, Severity

ESLINT = TOOLS_BY_NAME["eslint"]
STRICT_PRESET_NAME = "@typescript-eslint/strict-type-checked"
STRICT_PRESETS = (STRICT_PRESET_NAME, f"plugin:{STRICT_PRESET_NAME}")
REACT_PRESETS = ("plugin:react-hooks/recommended", "plugin:jsx-a11y/recommended", "plugin:jsx-a11y/strict")
REACT_HOOKS_PRESET = REACT_PRESETS[0]
JSX_A11Y_PRESETS = REACT_PRESETS[1:]
REACT_HOOKS_RULES = ("react-hooks/rules-of-hooks", "react-hooks/exhaustive-deps")
JSX_A11Y_RULE = "jsx-a11y/alt-text"
BASE_PRESET_RULES = (
    "@typescript-eslint/no-floating-promises",
    "@typescript-eslint/no-explicit-any",
)
FIRST_LINE = 1
ESLINT_FIX = (
    "enable @typescript-eslint/strict-type-checked, no-floating-promises, and no-explicit-any"
    " (plus react-hooks and jsx-a11y in React projects)"
)
UNPROVED_PRESET = "the explicit rules do not prove the @typescript-eslint/strict-type-checked preset"
UNKNOWN_EXTENDS = "the extends configuration does not include a supported strict preset"


def eslint_configured(project: Project) -> bool:
    manifest = project.root_manifest(ESLINT.ecosystem)
    if manifest is None or not is_typescript(project, project.manifests[ESLINT.ecosystem]):
        return False
    return is_configured(ESLINT, [manifest], project.entries)


def rule_enabled(severity: object) -> bool:
    if isinstance(severity, list):
        return bool(severity) and not isinstance(severity[0], bool) and severity[0] in ("error", "warn", 1, 2)
    return not isinstance(severity, bool) and severity in ("error", "warn", 1, 2)


def enabled_rule_names(document: dict[str, object]) -> set[str]:
    return {rule for rule, severity in table(document, "rules").items() if rule_enabled(severity)}


def disabled_rules(document: dict[str, object]) -> set[str]:
    return {rule for rule, severity in table(document, "rules").items() if not rule_enabled(severity)}


def extends_values(document: dict[str, object]) -> list[object]:
    value = document.get("extends")
    return [value] if isinstance(value, str) else array(document, "extends")


def has_preset(document: dict[str, object], presets: tuple[str, ...]) -> bool:
    return any(preset in presets for preset in extends_values(document) if isinstance(preset, str))


def react_declared(project: Project) -> bool:
    manifest = project.root_manifest(ESLINT.ecosystem)
    return manifest is not None and bool({"react", "react-dom"} & manifest.dependencies)


def base_shortfall(document: dict[str, object]) -> tuple[list[str], str]:
    if has_preset(document, STRICT_PRESETS):
        return [rule for rule in BASE_PRESET_RULES if rule in disabled_rules(document)], ""
    if extends_values(document):
        return [], UNKNOWN_EXTENDS
    if set(BASE_PRESET_RULES).issubset(enabled_rule_names(document)):
        return [], UNPROVED_PRESET
    return [STRICT_PRESET_NAME], ""


def react_shortfall(project: Project, document: dict[str, object]) -> list[str]:
    if not react_declared(project):
        return []
    disabled = disabled_rules(document)
    missing = []
    if not has_preset(document, (REACT_HOOKS_PRESET,)) or any(rule in disabled for rule in REACT_HOOKS_RULES):
        missing.append("react-hooks")
    if not has_preset(document, JSX_A11Y_PRESETS) or JSX_A11Y_RULE in disabled:
        missing.append("jsx-a11y")
    return missing


def lint_finding(project: Project, path: str, message: str, severity: Severity, kind: FindingKind) -> Finding:
    return Finding(project.shown(path), FIRST_LINE, CHECK_ID, severity, message, kind)


def eslint_shortfall(project: Project) -> list[Finding]:
    if not eslint_configured(project):
        return []
    unsupported = unsupported_config(project, project.manifests[ESLINT.ecosystem])
    if unsupported is not None:
        path, limitation = unsupported
        message = f"cannot verify that the ESLint rule sets are configured: {path} {limitation}"
        return [lint_finding(project, path, message, Severity.WARNING, FindingKind.VERIFICATION)]
    path = config_path(project)
    try:
        document = (
            package_config(project.root_manifest(ESLINT.ecosystem))
            if path == PACKAGE_CONFIG
            else read_config(project, path)
        )
        missing, reason = base_shortfall(document)
        if not reason:
            missing.extend(react_shortfall(project, document))
    except UnverifiedConfigError as error:
        message = f"cannot verify that the ESLint rule sets are configured: {error.reason}"
        return [lint_finding(project, error.path, message, Severity.WARNING, FindingKind.VERIFICATION)]
    if not missing and reason:
        message = f"cannot verify that the ESLint rule sets are configured: {reason}"
        return [lint_finding(project, path, message, Severity.WARNING, FindingKind.VERIFICATION)]
    if not missing:
        return []
    message = f"ESLint does not enable the required rule sets ({', '.join(missing)}); {ESLINT_FIX}"
    return [lint_finding(project, path, message, Severity.ERROR, FindingKind.CODE)]
