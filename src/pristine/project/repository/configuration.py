from collections.abc import Callable
from dataclasses import dataclass
from fnmatch import fnmatchcase

from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import Manifest
from pristine.project.repository.tools import Ecosystem, Role, Tool

TYPESCRIPT_CONFIG = "tsconfig.json"
TYPESCRIPT_PACKAGE = "typescript"
QUALITY_RULE_ID = "TL-3"


@dataclass(frozen=True)
class Requirement:
    ecosystem: Ecosystem
    role: Role
    applies: Callable[[Project, list[Manifest]], bool]


def every_project(_: Project, __: list[Manifest]) -> bool:
    return True


def is_typescript(project: Project, manifests: list[Manifest]) -> bool:
    declared = any(TYPESCRIPT_PACKAGE in manifest.dependencies for manifest in manifests)
    return declared or bool(project.files_named((TYPESCRIPT_CONFIG,))) or TYPESCRIPT_CONFIG in project.entries


REQUIREMENTS = (
    Requirement(Ecosystem.PYTHON, Role.FORMATTER, every_project),
    Requirement(Ecosystem.PYTHON, Role.LINTER, every_project),
    Requirement(Ecosystem.PYTHON, Role.TYPE_CHECKER, every_project),
    Requirement(Ecosystem.JAVASCRIPT, Role.FORMATTER, every_project),
    Requirement(Ecosystem.JAVASCRIPT, Role.LINTER, every_project),
    Requirement(Ecosystem.JAVASCRIPT, Role.TYPE_CHECKER, is_typescript),
    Requirement(Ecosystem.GO, Role.FORMATTER, every_project),
    Requirement(Ecosystem.GO, Role.LINTER, every_project),
    Requirement(Ecosystem.GO, Role.TYPE_CHECKER, every_project),
    Requirement(Ecosystem.RUST, Role.FORMATTER, every_project),
    Requirement(Ecosystem.RUST, Role.LINTER, every_project),
    Requirement(Ecosystem.RUST, Role.TYPE_CHECKER, every_project),
    *(Requirement(ecosystem, Role.DEAD_CODE, every_project) for ecosystem in Ecosystem),
)


def declares(manifest: Manifest, tool: Tool) -> bool:
    return bool(tool.packages & manifest.dependencies or manifest.settings.keys() & set(tool.settings_keys))


def is_configured(tool: Tool, manifests: list[Manifest], file_names: frozenset[str]) -> bool:
    has_config_file = any(fnmatchcase(name, pattern) for name in file_names for pattern in tool.config_files)
    return has_config_file or any(declares(manifest, tool) for manifest in manifests)
