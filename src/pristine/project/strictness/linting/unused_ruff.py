from pristine.project.commands.tool_arguments import checking, option, option_values, subcommand
from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import array, table
from pristine.project.strictness.linting.ruff_settings import config_path, lint_settings, universal_per_file_rules
from pristine.project.strictness.strictness import Arguments, Shortfall, UnverifiedConfigError

UNUSED_RULES = ("F401", "F841")


def selectors(arguments: list[str], lint: dict[str, object], field: str) -> set[str]:
    values = option_values(arguments, f"--{field}")
    configured = array(lint, field) if field in lint or field != "select" else ["F"]
    if field != "select" and option_values(arguments, "--select"):
        configured = []
    source = values if values else configured
    return {prefix for value in source if isinstance(value, str) for prefix in value.split(",") if prefix}


def specificity(rule: str, selectors: set[str]) -> int:
    return max(
        (len(prefix) if prefix != "ALL" else 0 for prefix in selectors if prefix == "ALL" or rule.startswith(prefix)),
        default=-1,
    )


def unused_ruff_shortfall(project: Project, calls: Arguments) -> Shortfall | None:
    path = config_path(project)
    lint = table(lint_settings(project, path, frozenset()), "lint")
    for arguments in calls:
        if not checking(arguments) or not subcommand("check")(arguments):
            continue
        if option("--config", "--isolated")(arguments):
            raise UnverifiedConfigError(
                path, "review the explicit Ruff configuration or isolated command for unused-code checking"
            )
        selected = selectors(arguments, lint, "select") | selectors(arguments, lint, "extend-select")
        ignored = selectors(arguments, lint, "ignore") | selectors(arguments, lint, "extend-ignore")
        masked = universal_per_file_rules(lint)
        enabled = all(
            specificity(rule, selected) > specificity(rule, ignored) and specificity(rule, masked) == -1
            for rule in UNUSED_RULES
        )
        if enabled:
            return None
    return Shortfall(
        path,
        "enable Ruff F401 and F841 in the invoked command and configuration, or run another dead-code checker; these are limited native unused-import and unused-local checks",
    )
