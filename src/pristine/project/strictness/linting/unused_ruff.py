from posixpath import normpath

from pristine.files.path_roles import is_test_path
from pristine.project.commands.gates import fast_gate
from pristine.project.commands.shell import program_calls, root_working_directory, source_arguments
from pristine.project.commands.tool_arguments import option, option_values, ruff_checking
from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import array, table
from pristine.project.strictness.linting.ruff_settings import (
    config_path,
    lint_settings,
    universal_per_file_rules,
    verify_source_configurations,
)
from pristine.project.strictness.source_selection import python_sources, source_target, verify_python_sources
from pristine.project.strictness.strictness import Arguments, Shortfall, UnverifiedConfigError

UNUSED_RULES = ("F401", "F841")
SOURCE_OPTIONS = frozenset(
    {
        "--select",
        "--extend-select",
        "--ignore",
        "--extend-ignore",
        "--line-length",
        "--target-version",
        "--output-format",
        "--output-file",
        "--exclude",
        "--extend-exclude",
    }
)
SOURCE_SETTINGS = frozenset({"include", "extend-include", "exclude", "extend-exclude", "force-exclude"})
SUPPRESSION_SETTINGS = frozenset({"dummy-variable-rgx", "pyflakes"})


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
    settings = lint_settings(project, path, frozenset())
    lint = table(settings, "lint")
    for arguments in calls:
        if not ruff_checking(arguments):
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
            verify_ruff_scope(project, path, arguments, settings)
            return None
    return Shortfall(
        path,
        "enable Ruff F401 and F841 in the invoked command and configuration, or run another dead-code checker; these are limited native unused-import and unused-local checks",
    )


def verify_ruff_scope(project: Project, config: str, arguments: list[str], settings: dict[str, object]) -> None:
    gate = fast_gate(project)
    commands = gate.commands if gate else ()
    if any(
        not root_working_directory(command) for command in commands if list(program_calls(command, frozenset({"ruff"})))
    ):
        raise UnverifiedConfigError(config, "review Ruff source paths relative to the changed working directory")
    if (
        (SOURCE_SETTINGS | SUPPRESSION_SETTINGS) & settings.keys()
        or (SOURCE_SETTINGS | SUPPRESSION_SETTINGS) & table(settings, "lint").keys()
        or any(settings.get(mode) and not option(f"--no-{mode}")(arguments) for mode in ("fix", "fix-only"))
        or option(
            "--exclude",
            "--extend-exclude",
            "--force-exclude",
            "--stdin-filename",
            "--per-file-ignores",
            "--extend-per-file-ignores",
        )(arguments)
        or "-" in arguments
    ):
        raise UnverifiedConfigError(
            config,
            "review Ruff source inclusion, exclusions, fixing, suppressions or stdin before certifying unused-code checking",
        )
    verify_source_configurations(project, config, python_sources(project))
    verify_unused_masks(project, config, table(settings, "lint"))
    sources = source_arguments(arguments[1:], SOURCE_OPTIONS) or ["."]
    paths = [source_target(project, config, source) for source in sources]
    verify_python_sources(project, config, paths, [], "Ruff")


def verify_unused_masks(project: Project, config: str, lint: dict[str, object]) -> None:
    application = any(not is_test_path(PurePosixPath(source)) for source in python_sources(project))
    masks = [*table(lint, "per-file-ignores").items(), *table(lint, "extend-per-file-ignores").items()]
    for pattern, rules in masks:
        selectors = {rule for rule in rules if isinstance(rule, str)} if isinstance(rules, list) else set[str]()
        unused = any(specificity(rule, selectors) != -1 for rule in UNUSED_RULES)
        test_only = application and "!" not in pattern and is_test_path(PurePosixPath(normpath(pattern)))
        if unused and not test_only:
            raise UnverifiedConfigError(
                config,
                "review per-file unused-rule masks against application sources or keep required unused rules enabled",
            )


from pathlib import PurePosixPath
