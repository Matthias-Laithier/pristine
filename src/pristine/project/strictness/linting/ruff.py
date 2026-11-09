from pristine.project.repository.configuration import QUALITY_RULE_ID as RULE_ID
from pristine.project.repository.configuration import is_configured
from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import array, table
from pristine.project.repository.tools import TOOLS_BY_NAME
from pristine.project.strictness.linting.ruff_settings import (
    config_path,
    lint_settings,
    selected_rules,
    universal_per_file_rules,
)
from pristine.project.strictness.strictness import UnverifiedConfigError
from pristine.reports.findings import Finding, FindingKind, Severity

RUFF = TOOLS_BY_NAME["ruff"]
REQUIRED_RULES = ("S", "ASYNC", "DTZ", "G", "T20")
ALL_RULES = "ALL"
FIRST_LINE = 1
RUFF_FIX = 'select or extend-select the S, ASYNC, DTZ, G, and T20 rule sets (or "ALL")'


def missing_rules(settings: dict[str, object]) -> list[str]:
    selected = {rule for rule in selected_rules(settings) if isinstance(rule, str)}
    lint = table(settings, "lint")
    ignored = {rule for rule in [*array(lint, "ignore"), *array(lint, "extend-ignore")] if isinstance(rule, str)}
    ignored.update(universal_per_file_rules(lint))
    if ALL_RULES in selected:
        selected = set() if ALL_RULES in ignored else set(REQUIRED_RULES)
    return [rule for rule in REQUIRED_RULES if rule not in selected or rule in ignored]


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
