from collections.abc import Iterable, Mapping

from pristine.project.commands.shell import positionals, program_calls

SCRIPT_RUNNERS = frozenset({"npm", "pnpm", "yarn", "bun"})
RUN_COMMANDS = frozenset({"run", "run-script"})
DIRECT_SCRIPT_RUNNERS = frozenset({"pnpm", "yarn"})
NPM = "npm"
NPM_SCRIPT_ALIASES = {"test": "test", "t": "test", "start": "start"}
OTHER_PACKAGE_OPTIONS = ("--prefix", "-C", "--dir", "--cwd", "--filter", "-F", "-w", "--workspace", "-r", "--recursive")


def invoked_script(runner: str, arguments: list[str]) -> str | None:
    words = positionals(arguments)
    if not words or any(argument.startswith(OTHER_PACKAGE_OPTIONS) for argument in arguments):
        return None
    if words[0] in RUN_COMMANDS:
        return words[1] if len(words) > 1 else None
    if runner in DIRECT_SCRIPT_RUNNERS:
        return words[0]
    return NPM_SCRIPT_ALIASES.get(words[0]) if runner == NPM else None


def script_names(command: str) -> set[str]:
    calls = program_calls(command, SCRIPT_RUNNERS)
    return {name for runner, arguments in calls if (name := invoked_script(runner, arguments)) is not None}


def with_package_scripts(commands: Iterable[str], scripts: Mapping[str, str]) -> list[str]:
    visited: set[str] = set()
    pending = list(commands)
    expanded = list(pending)
    while pending:
        names = {name for name in script_names(pending.pop()) if name in scripts} - visited
        visited |= names
        pending.extend(scripts[name] for name in sorted(names))
    return [*expanded, *(scripts[name] for name in sorted(visited))]
