import tomllib

from pristine.project.commands.tool_arguments import option_values, source_arguments
from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import table
from pristine.project.repository.tools import Ecosystem
from pristine.project.strictness.strictness import Arguments, Shortfall, UnverifiedConfigError

VALUE_OPTIONS = frozenset({"--config", "--exclude", "--ignore-decorators", "--ignore-names", "--min-confidence"})


def configuration(project: Project, arguments: list[str]) -> tuple[str, dict[str, object]]:
    manifest = project.root_manifest(Ecosystem.PYTHON)
    explicit = option_values(arguments, "--config")
    if not explicit:
        return (manifest.path, table(manifest.settings, "vulture")) if manifest else ("pyproject.toml", {})
    path = explicit[-1]
    if not project.reader.is_local_file(path):
        raise UnverifiedConfigError(path, "Vulture configuration is not a readable file of the repository")
    text = project.reader.text(path)
    if text is None:
        raise UnverifiedConfigError(path, "Vulture configuration is unreadable")
    try:
        return path, table(table(tomllib.loads(text), "tool"), "vulture")
    except ValueError as error:
        raise UnverifiedConfigError(path, f"Vulture configuration is invalid TOML ({error})") from error


def vulture_shortfall(project: Project, calls: Arguments) -> Shortfall | None:
    if len(calls) != 1:
        raise UnverifiedConfigError("pyproject.toml", "multiple Vulture invocations require source-scope review")
    arguments = calls[0]
    path, settings = configuration(project, arguments)
    options = option_values(arguments, "--exclude")
    excluded = options[-1].split(",") if options else settings.get("exclude")
    if isinstance(excluded, list) and any(value in {"*", "**"} for value in excluded if isinstance(value, str)):
        return Shortfall(path, "remove the all-source exclusion from Vulture's exclude setting or --exclude option")
    targets = source_arguments(arguments, VALUE_OPTIONS) or settings.get("paths", [])
    if not isinstance(targets, list) or not any(
        project.reader.is_local_path(target) for target in targets if isinstance(target, str)
    ):
        raise UnverifiedConfigError(
            path, "Vulture has no verifiable local source paths; pass source paths or configure tool.vulture.paths"
        )
    return None
