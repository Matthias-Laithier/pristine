from collections.abc import Callable, Iterable
from dataclasses import dataclass
from fnmatch import fnmatchcase

from pristine.project.commands.scripts import with_package_scripts
from pristine.project.commands.shell import guarded_program_calls, program_calls
from pristine.project.repository.loading import Project
from pristine.project.repository.makefile import FAST_GATE, reach
from pristine.project.repository.makefile_syntax import Rule
from pristine.project.repository.manifests import Manifest
from pristine.project.repository.tools import TOOLS, TOOLS_BY_NAME, Ecosystem, Role, Tool
from pristine.reports.findings import Finding, Severity

RULE_ID = "TL-3"
FIRST_LINE = 1
TYPESCRIPT_CONFIG = "tsconfig.json"
TYPESCRIPT_PACKAGE = "typescript"
TOOL_NAMES = frozenset(TOOLS_BY_NAME)
RUN_DESCRIPTIONS = {
    Role.FORMATTER: "the formatter in check mode, verifying formatting without rewriting files",
    Role.LINTER: "the linter",
    Role.TYPE_CHECKER: "the type checker",
}

type Invocation = tuple[str, Role]


@dataclass(frozen=True)
class Requirement:
    ecosystem: Ecosystem
    role: Role
    applies: Callable[[Project, list[Manifest]], bool]


@dataclass(frozen=True)
class FastGate:
    rule: Rule
    commands: tuple[str, ...]
    invocations: frozenset[Invocation]


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
)


def invocations(commands: Iterable[str]) -> frozenset[Invocation]:
    normal_calls = [
        (name, tuple(arguments)) for command in commands for name, arguments in program_calls(command, TOOL_NAMES)
    ]
    guarded_calls = {
        (name, tuple(arguments))
        for command in commands
        for name, arguments in guarded_program_calls(command, TOOL_NAMES)
    }
    calls = normal_calls + [*guarded_calls]
    return frozenset(
        (name, role)
        for name, arguments in calls
        for role, test in TOOLS_BY_NAME[name].checks.items()
        if test(list(arguments))
        and (
            role is not Role.FORMATTER
            or TOOLS_BY_NAME[name].ecosystem is not Ecosystem.GO
            or (name, arguments) in guarded_calls
        )
    )


def fast_gate(project: Project) -> FastGate | None:
    makefile = project.makefile
    if makefile is None or FAST_GATE not in makefile.rules:
        return None
    javascript = project.root_manifest(Ecosystem.JAVASCRIPT)
    commands = with_package_scripts(reach(makefile, FAST_GATE).commands, javascript.scripts if javascript else {})
    return FastGate(makefile.rules[FAST_GATE], tuple(commands), invocations(commands))


def declares(manifest: Manifest, tool: Tool) -> bool:
    return bool(tool.packages & manifest.dependencies or manifest.settings.keys() & set(tool.settings_keys))


def is_configured(tool: Tool, manifests: list[Manifest], file_names: frozenset[str]) -> bool:
    has_config_file = any(fnmatchcase(name, pattern) for name in file_names for pattern in tool.config_files)
    return has_config_file or any(declares(manifest, tool) for manifest in manifests)


def unmet(project: Project, requirement: Requirement, gate: FastGate | None) -> list[Finding]:
    manifest = project.root_manifest(requirement.ecosystem)
    manifests = project.manifests[requirement.ecosystem]
    if manifest is None or not requirement.applies(project, manifests):
        return []
    candidates = [tool for tool in TOOLS if tool.ecosystem is requirement.ecosystem and requirement.role in tool.checks]
    if gate and any((tool.name, requirement.role) in gate.invocations for tool in candidates):
        return []
    file_names = project.file_names
    configured = [tool.name for tool in candidates if is_configured(tool, manifests, file_names)]
    if not configured:
        names = ", ".join(tool.name for tool in candidates)
        message = (
            f"no {requirement.ecosystem} {requirement.role} configured; declare one of {names} and run it in make check"
        )
        return [Finding(project.shown(manifest.path), FIRST_LINE, RULE_ID, Severity.ERROR, message)]
    if gate is None:
        return []
    message = f"make check does not run {RUN_DESCRIPTIONS[requirement.role]} (configured: {', '.join(configured)})"
    return [Finding(project.shown(gate.rule.path), gate.rule.line, RULE_ID, Severity.ERROR, message)]


def automated_quality_checks(project: Project) -> list[Finding]:
    gate = fast_gate(project)
    return [finding for requirement in REQUIREMENTS for finding in unmet(project, requirement, gate)]


CHECKS = (automated_quality_checks,)
