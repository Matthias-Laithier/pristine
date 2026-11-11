from collections.abc import Callable
from dataclasses import dataclass

from pristine.project.commands.scripts import with_package_scripts
from pristine.project.commands.shell import positionals, program_calls
from pristine.project.repository.loading import Project
from pristine.project.repository.makefile import Makefile
from pristine.project.repository.makefile_syntax import Rule
from pristine.project.repository.tools import Ecosystem
from pristine.reports.findings import Finding, Severity

CHECK_ID = "PROJ-4"
NPM_LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json")
UV_FROZEN_VARIABLES = ("UV_FROZEN", "UV_LOCKED")
GLOBAL_OPTIONS = ("-g", "--global")
NPM_LOCK_BYPASS_OPTIONS = (*GLOBAL_OPTIONS, "--no-save", "--no-package-lock")
BARE_COMMAND = ""
YARN_FROZEN_OPTIONS = ("--immutable", "--frozen-lockfile")
PNPM_FROZEN_OPTIONS = ("--frozen-lockfile",)

type Applies = Callable[[Project, list[str]], bool]


@dataclass(frozen=True)
class Installer:
    program: str
    unfrozen_form: str
    commands: frozenset[str]
    frozen_options: tuple[str, ...]
    frozen_form: str
    applies: Applies


def uv_applies(project: Project, _: list[str]) -> bool:
    makefile = project.makefile
    return makefile is None or not any(name in makefile.variables for name in UV_FROZEN_VARIABLES)


def npm_applies(project: Project, arguments: list[str]) -> bool:
    has_lockfile = bool(project.files_named(NPM_LOCKFILES))
    return has_lockfile and len(positionals(arguments)) == 1 and not set(arguments) & set(NPM_LOCK_BYPASS_OPTIONS)


def project_install(_: Project, arguments: list[str]) -> bool:
    return len(positionals(arguments)) <= 1 and not set(arguments) & set(GLOBAL_OPTIONS)


INSTALLERS = {
    installer.program: installer
    for installer in (
        Installer("uv", "uv sync", frozenset({"sync"}), ("--locked", "--frozen"), "uv sync --locked", uv_applies),
        Installer("npm", "npm install", frozenset({"install", "i"}), (), "npm ci", npm_applies),
        Installer(
            "pnpm",
            "pnpm install",
            frozenset({"install", "i"}),
            PNPM_FROZEN_OPTIONS,
            "pnpm install --frozen-lockfile",
            project_install,
        ),
        Installer(
            "yarn",
            "yarn install",
            frozenset({"install", BARE_COMMAND}),
            YARN_FROZEN_OPTIONS,
            "yarn install --immutable",
            project_install,
        ),
    )
}
INSTALLER_NAMES = frozenset(INSTALLERS)


def unfrozen_install(project: Project, command: str) -> Installer | None:
    for program, arguments in program_calls(command, INSTALLER_NAMES):
        installer = INSTALLERS[program]
        subcommand = next(iter(positionals(arguments)), None if arguments else BARE_COMMAND)
        frozen = any(argument.split("=", 1)[0] in installer.frozen_options for argument in arguments)
        if subcommand in installer.commands and not frozen and installer.applies(project, arguments):
            return installer
    return None


def rule_findings(project: Project, makefile: Makefile, rule: Rule) -> list[Finding]:
    javascript = project.root_manifest(Ecosystem.JAVASCRIPT)
    recipe = [makefile.expand(line) for line in rule.recipe]
    commands = with_package_scripts(recipe, javascript.scripts if javascript else {})
    installers = dict.fromkeys(found for command in commands if (found := unfrozen_install(project, command)))
    messages = (
        f"'{installer.unfrozen_form}' can rewrite the lockfile; install in frozen mode with '{installer.frozen_form}'"
        for installer in installers
    )
    return [Finding(project.shown(rule.path), rule.line, CHECK_ID, Severity.ERROR, message) for message in messages]


def unfrozen_installs(project: Project) -> list[Finding]:
    makefile = project.makefile
    if makefile is None:
        return []
    rules = {id(rule): rule for rule in makefile.rules.values()}.values()
    return [finding for rule in rules for finding in rule_findings(project, makefile, rule)]


CHECKS = (unfrozen_installs,)
