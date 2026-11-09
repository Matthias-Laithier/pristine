from collections.abc import Iterable
from dataclasses import dataclass

from pristine.project.commands.scripts import with_package_scripts
from pristine.project.commands.shell import guarded_program_calls, program_calls
from pristine.project.repository.loading import Project
from pristine.project.repository.makefile import FAST_GATE, reach
from pristine.project.repository.makefile_syntax import Rule
from pristine.project.repository.tools import TOOLS_BY_NAME, Ecosystem, Role

TOOL_NAMES = frozenset(TOOLS_BY_NAME)
type Invocation = tuple[str, Role]


@dataclass(frozen=True)
class FastGate:
    rule: Rule
    commands: tuple[str, ...]
    invocations: frozenset[Invocation]
    ignores_failures: bool = False


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
    reached = reach(makefile, FAST_GATE)
    commands = with_package_scripts(reached.commands, javascript.scripts if javascript else {})
    ignored = any(makefile.rules[target].ignores_failures for target in reached.targets)
    return FastGate(makefile.rules[FAST_GATE], tuple(commands), invocations(commands), ignored)
