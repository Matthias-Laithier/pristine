from collections.abc import Iterable
from dataclasses import dataclass

from pristine.project.commands.scripts import SCRIPT_RUNNERS, with_package_scripts
from pristine.project.commands.shell import (
    guarded_program_calls,
    program_calls,
    root_working_directory,
    verifiable_command,
)
from pristine.project.repository.loading import Project
from pristine.project.repository.makefile import FAST_GATE, reach
from pristine.project.repository.makefile_syntax import Rule
from pristine.project.repository.tools import TOOLS_BY_NAME, Ecosystem, Role

TOOL_NAMES = frozenset(TOOLS_BY_NAME)
RELAY_PROGRAMS = SCRIPT_RUNNERS | {"make", "gmake"}
MAKE_RELAY_FLAGS = frozenset(
    {"-s", "--silent", "--quiet", "-w", "--print-directory", "--no-print-directory", "-k", "--keep-going"}
)
SCRIPT_RELAY_FLAGS = frozenset({"-s", "--silent", "--quiet"})
type Invocation = tuple[str, Role]


@dataclass(frozen=True)
class Gate:
    rule: Rule
    commands: tuple[str, ...]
    invocations: frozenset[Invocation]
    ignores_failures: bool = False
    unverified_relays: bool = False


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


def quality_gate(project: Project, target: str) -> Gate | None:
    makefile = project.makefile
    if makefile is None or target not in makefile.rules:
        return None
    javascript = project.root_manifest(Ecosystem.JAVASCRIPT)
    reached = reach(makefile, target)
    commands = with_package_scripts(reached.commands, javascript.scripts if javascript else {})
    ignored = any(makefile.rules[target].ignored_error_commands for target in reached.targets)
    relayed = any(not verifiable_relay(command) for command in commands)
    return Gate(makefile.rules[target], tuple(commands), invocations(commands), ignored, relayed)


def fast_gate(project: Project) -> Gate | None:
    return quality_gate(project, FAST_GATE)


def verifiable_context(project: Project, gate: Gate, command: str) -> bool:
    return (
        not gate.ignores_failures
        and not gate.unverified_relays
        and not bool(project.makefile and (project.makefile.has_conditionals or project.makefile.unverified_recipes))
        and root_working_directory(command)
        and verifiable_command(command)
    )


def verifiable_relay(command: str) -> bool:
    calls = list(program_calls(command, RELAY_PROGRAMS))
    if calls and (not verifiable_command(command) or not root_working_directory(command)):
        return False
    for name, arguments in calls:
        allowed = MAKE_RELAY_FLAGS if name in {"make", "gmake"} else SCRIPT_RELAY_FLAGS
        invalid = any(
            (argument.startswith("-") and argument not in allowed) or "=" in argument for argument in arguments
        )
        if invalid:
            return False
    return True
