from pristine.project.commands.gates import Gate, fast_gate
from pristine.project.commands.scripts import SCRIPT_RUNNERS
from pristine.project.commands.shell import (
    program_calls,
    program_name,
    root_working_directory,
    verifiable_command,
    words_of,
)
from pristine.project.repository.configuration import REQUIREMENTS, Requirement, is_configured
from pristine.project.repository.loading import Project
from pristine.project.repository.tools import TOOLS, Ecosystem, Role, Tool
from pristine.project.strictness.linting.unused_ruff import unused_ruff_shortfall
from pristine.project.strictness.strictness import UnverifiedConfigError
from pristine.project.strictness.typescript_strictness import TYPESCRIPT_PROBES, unused_typescript_shortfall
from pristine.reports.findings import Finding, FindingKind, Severity

RULE_ID = "TL-3"
FIRST_LINE = 1
RUN_DESCRIPTIONS = {
    Role.FORMATTER: "the formatter in check mode, verifying formatting without rewriting files",
    Role.LINTER: "the linter",
    Role.TYPE_CHECKER: "the type checker",
    Role.DEAD_CODE: "an applicable dead-code checker (including limited native unused-code checks)",
}


def uncertain_gate(project: Project, candidates: list[Tool], gate: Gate) -> bool:
    names = {tool.name for tool in candidates}
    names |= {"npm", "pnpm", "yarn", "bun", "make", "gmake"}
    if any(tool.ecosystem is Ecosystem.JAVASCRIPT for tool in candidates):
        names |= set(TYPESCRIPT_PROBES)
    return (
        gate.ignores_failures
        or gate.unverified_relays
        or bool(project.makefile and (project.makefile.has_conditionals or project.makefile.unverified_recipes))
        or any(
            (not verifiable_command(command) and names & {program_name(word) for word in words_of(command)})
            or (
                not root_working_directory(command)
                and bool(list(program_calls(command, SCRIPT_RUNNERS | {"make", "gmake"})))
            )
            for command in gate.commands
        )
    )


def uncertain_dead_code(project: Project, requirement: Requirement, gate: Gate | None) -> Finding | None:
    if requirement.role is not Role.DEAD_CODE or gate is None:
        return None
    candidates = [tool for tool in TOOLS if tool.ecosystem is requirement.ecosystem and requirement.role in tool.checks]
    if not uncertain_gate(project, candidates, gate):
        return None
    message = "cannot verify dead-code checking in make check: conditional, dynamic, piped or failure-suppressing commands require review"
    return Finding(
        project.shown(gate.rule.path), gate.rule.line, RULE_ID, Severity.WARNING, message, FindingKind.VERIFICATION
    )


def native_dead_code(project: Project, gate: Gate, ecosystem: Ecosystem) -> list[Finding]:
    names = frozenset({"ruff"}) if ecosystem is Ecosystem.PYTHON else frozenset(TYPESCRIPT_PROBES)
    check = unused_ruff_shortfall if ecosystem is Ecosystem.PYTHON else unused_typescript_shortfall
    calls = [arguments for command in gate.commands for _, arguments in program_calls(command, names)]
    try:
        shortfall = check(project, calls)
    except UnverifiedConfigError as error:
        return [
            Finding(
                project.shown(error.path),
                FIRST_LINE,
                RULE_ID,
                Severity.WARNING,
                f"cannot verify native {ecosystem} dead-code checking: {error.reason}",
                FindingKind.VERIFICATION,
            )
        ]
    if shortfall is None:
        return []
    return [
        Finding(
            project.shown(gate.rule.path),
            gate.rule.line,
            RULE_ID,
            Severity.ERROR,
            f"make check does not enforce dead-code checking; {shortfall.fix}",
        )
    ]


def unmet(project: Project, requirement: Requirement, gate: Gate | None) -> list[Finding]:
    manifest = project.root_manifest(requirement.ecosystem)
    manifests = project.manifests[requirement.ecosystem]
    if (
        manifest is None
        or not requirement.applies(project, manifests)
        or (requirement.role is Role.DEAD_CODE and gate is None)
    ):
        return []
    candidates = [tool for tool in TOOLS if tool.ecosystem is requirement.ecosystem and requirement.role in tool.checks]
    uncertainty = uncertain_dead_code(project, requirement, gate)
    if uncertainty:
        return [uncertainty]
    if gate and any((tool.name, requirement.role) in gate.invocations for tool in candidates):
        return []
    if (
        gate
        and requirement.role is Role.DEAD_CODE
        and requirement.ecosystem is Ecosystem.JAVASCRIPT
        and any((name, Role.TYPE_CHECKER) in gate.invocations for name in TYPESCRIPT_PROBES)
    ):
        return native_dead_code(project, gate, requirement.ecosystem)
    if (
        gate
        and requirement.role is Role.DEAD_CODE
        and requirement.ecosystem is Ecosystem.PYTHON
        and ("ruff", Role.LINTER) in gate.invocations
    ):
        return native_dead_code(project, gate, requirement.ecosystem)
    return missing_tool(project, requirement, candidates, gate)


def missing_tool(
    project: Project, requirement: Requirement, candidates: list[Tool], gate: Gate | None
) -> list[Finding]:
    manifest = project.root_manifest(requirement.ecosystem)
    if manifest is None:
        return []
    configured = [
        tool.name
        for tool in candidates
        if is_configured(tool, project.manifests[requirement.ecosystem], project.file_names)
    ]
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
