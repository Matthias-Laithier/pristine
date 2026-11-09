import tomllib
from pathlib import Path

from pristine.project.commands.gates import fast_gate
from pristine.project.commands.shell import program_calls, root_working_directory, source_arguments
from pristine.project.commands.tool_arguments import option_values
from pristine.project.repository.loading import Project
from pristine.project.strictness.source_selection import source_target, verify_python_sources
from pristine.project.strictness.strictness import Arguments, Shortfall, UnverifiedConfigError

VALUE_OPTIONS = frozenset({"--config", "--exclude", "--ignore-decorators", "--ignore-names", "--min-confidence"})
MAX_CONFIDENCE = 100
SETTING_TYPES = {
    "config": str,
    "min_confidence": int,
    "paths": list,
    "exclude": list,
    "ignore_names": list,
    "ignore_decorators": list,
    "make_whitelist": bool,
    "sort_by_size": bool,
    "verbose": bool,
}


def configuration(project: Project, arguments: list[str]) -> tuple[str, dict[str, object]]:
    explicit = option_values(arguments, "--config")
    path = explicit[-1] if explicit else "pyproject.toml"
    if not project.reader.is_local_file(path):
        if explicit:
            raise UnverifiedConfigError(path, "Vulture configuration is not a readable file of the repository")
        return path, {}
    text = project.reader.text(path)
    if text is None:
        raise UnverifiedConfigError(path, "Vulture configuration is unreadable")
    try:
        tool: object = tomllib.loads(text).get("tool", {})
        if not isinstance(tool, dict):
            raise UnverifiedConfigError(path, "Vulture tool configuration must be a table")
        return path, validated_settings(path, tool.get("vulture", {}))
    except ValueError as error:
        raise UnverifiedConfigError(path, f"Vulture configuration is invalid TOML ({error})") from error


def validated_settings(config: str, settings: object) -> dict[str, object]:
    if not isinstance(settings, dict):
        raise UnverifiedConfigError(config, "Vulture configuration must be a table")
    for key, value in settings.items():
        if key not in SETTING_TYPES or type(value) is not SETTING_TYPES[key]:
            raise UnverifiedConfigError(
                config, f"Vulture configuration field {key} is unknown or has an invalid type before CLI overrides"
            )
    return dict[str, object](settings)


def vulture_shortfall(project: Project, calls: Arguments) -> Shortfall | None:
    if len(calls) != 1:
        raise UnverifiedConfigError("pyproject.toml", "multiple Vulture invocations require source-scope review")
    arguments = calls[0]
    path, settings = configuration(project, arguments)
    verify_working_directory(project, path)
    validate_confidence(path, arguments, settings)
    options = option_values(arguments, "--exclude")
    excluded = options[-1].split(",") if options else settings.get("exclude")
    if isinstance(excluded, list) and any(value in {"*", "**"} for value in excluded if isinstance(value, str)):
        return Shortfall(path, "remove the all-source exclusion from Vulture's exclude setting or --exclude option")
    targets, patterns = source_scope(project, path, arguments, settings)
    verify_python_sources(project, path, targets, patterns, "Vulture")
    return None


def source_scope(
    project: Project, path: str, arguments: list[str], settings: dict[str, object]
) -> tuple[list[Path], list[str]]:
    targets = source_arguments(arguments, VALUE_OPTIONS) or settings.get("paths", [])
    if not isinstance(targets, list) or not targets or any(not isinstance(target, str) for target in targets):
        raise UnverifiedConfigError(
            path, "Vulture has no verifiable local source paths; pass source paths or configure tool.vulture.paths"
        )
    options = option_values(arguments, "--exclude")
    excluded = options[-1].split(",") if options else settings.get("exclude")
    if excluded is not None and (
        not isinstance(excluded, list) or any(not isinstance(value, str) for value in excluded)
    ):
        raise UnverifiedConfigError(path, "Vulture exclude must be a list of patterns")
    selected = [source_target(project, path, target) for target in targets if isinstance(target, str)]
    patterns = (
        [
            pattern if any(marker in pattern for marker in "*?[") else f"*{pattern}*"
            for pattern in excluded
            if isinstance(pattern, str)
        ]
        if isinstance(excluded, list)
        else []
    )
    return selected, patterns


def verify_working_directory(project: Project, config: str) -> None:
    gate = fast_gate(project)
    commands = gate.commands if gate else ()
    relocated = any(
        not root_working_directory(command)
        for command in commands
        if list(program_calls(command, frozenset({"vulture"})))
    )
    if relocated:
        raise UnverifiedConfigError(
            config,
            "Vulture invocation changes working directory; review source and configuration paths relative to that directory",
        )


def validate_confidence(config: str, arguments: list[str], settings: dict[str, object]) -> None:
    values = option_values(arguments, "--min-confidence")
    try:
        confidence = int(values[-1]) if values else settings.get("min_confidence", 0)
    except ValueError as error:
        raise UnverifiedConfigError(config, "Vulture min_confidence must be an integer from 0 to 100") from error
    if not isinstance(confidence, int) or isinstance(confidence, bool) or not 0 <= confidence <= MAX_CONFIDENCE:
        raise UnverifiedConfigError(config, "Vulture min_confidence must be an integer from 0 to 100")
