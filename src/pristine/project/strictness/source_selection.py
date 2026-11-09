from fnmatch import fnmatchcase
from pathlib import Path, PurePath

from pristine.files.path_roles import is_test_path
from pristine.project.repository.loading import Project
from pristine.project.strictness.strictness import UnverifiedConfigError


def source_target(project: Project, config: str, target: str) -> Path:
    selected = project.reader.local_path(target)
    if selected is None:
        raise UnverifiedConfigError(config, f"source target {target} is not a path of the repository")
    return selected


def python_sources(project: Project) -> set[str]:
    python = {name for name in project.files if name.endswith(".py")}
    return {name for name in python if not is_test_path(PurePath(name))} or python


def verify_python_sources(project: Project, config: str, targets: list[Path], patterns: list[str], tool: str) -> None:
    application = python_sources(project)
    if not application:
        raise UnverifiedConfigError(config, f"no discovered Python sources establish {tool}'s analysis scope")
    selected = {
        name
        for name in application
        if any((project.root / name).resolve().is_relative_to(target) for target in targets)
        and not any(fnmatchcase(str((project.root / name).resolve()).lower(), pattern.lower()) for pattern in patterns)
    }
    missing = application - selected
    if missing:
        raise UnverifiedConfigError(
            config,
            f"{tool} does not select discovered Python source {min(missing)}; include applicable source paths or review targeted exclusions",
        )
