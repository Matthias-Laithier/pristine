from collections.abc import Iterable

from pristine.project.automation import RULE_ID
from pristine.project.commands.gates import Gate, fast_gate
from pristine.project.commands.shell import program_calls
from pristine.project.repository.configuration import declares, every_project, is_configured, is_typescript
from pristine.project.repository.loading import Project
from pristine.project.repository.tools import TOOLS, TOOLS_BY_NAME, Ecosystem, Role
from pristine.project.strictness.annotations import python_annotations
from pristine.project.strictness.dead_code import CHECKS as DEAD_CODE_CHECKS
from pristine.project.strictness.linting import LINT_CHECKS
from pristine.project.strictness.python_strictness import PYTHON_PROBES
from pristine.project.strictness.strictness import Arguments, UnverifiedConfigError
from pristine.project.strictness.typescript_strictness import TYPESCRIPT_PROBES
from pristine.reports.findings import Finding, FindingKind, Severity

FIRST_LINE = 1
PROBES = PYTHON_PROBES | TYPESCRIPT_PROBES
PROBED_NAMES = frozenset(PROBES)
APPLIES = {Ecosystem.PYTHON: every_project, Ecosystem.JAVASCRIPT: is_typescript}


def gate_calls(commands: Iterable[str]) -> dict[str, Arguments]:
    calls = [
        (name, arguments)
        for command in commands
        for name, arguments in program_calls(command, PROBED_NAMES)
        if TOOLS_BY_NAME[name].checks[Role.TYPE_CHECKER](arguments)
    ]
    return {name: [arguments for called, arguments in calls if called == name] for name, _ in calls}


def runs_type_checker(gate: Gate | None, ecosystem: Ecosystem) -> bool:
    return gate is not None and any(
        (tool.name, Role.TYPE_CHECKER) in gate.invocations for tool in TOOLS if tool.ecosystem is ecosystem
    )


def probed_checkers(
    project: Project, ecosystem: Ecosystem, gate: Gate | None, calls: dict[str, Arguments]
) -> list[str]:
    manifest = project.root_manifest(ecosystem)
    if manifest is None or not APPLIES[ecosystem](project, project.manifests[ecosystem]):
        return []
    names = [name for name in PROBES if TOOLS_BY_NAME[name].ecosystem is ecosystem]
    if runs_type_checker(gate, ecosystem):
        return [name for name in names if name in calls]
    declared = [name for name in names if declares(manifest, TOOLS_BY_NAME[name])]
    return declared or [name for name in names if is_configured(TOOLS_BY_NAME[name], [manifest], project.entries)]


def probe_finding(project: Project, name: str, calls: Arguments) -> Finding | None:
    probe = PROBES[name]
    try:
        shortfall = probe.check(project, calls)
    except UnverifiedConfigError as error:
        message = f"cannot verify that {probe.subject} type-checks in strict mode: {error.reason}"
        return Finding(
            project.shown(error.path),
            FIRST_LINE,
            RULE_ID,
            Severity.WARNING,
            message,
            FindingKind.VERIFICATION,
        )
    if shortfall is None:
        return None
    message = f"{probe.subject} does not type-check in strict mode; {shortfall.fix}"
    return Finding(project.shown(shortfall.path), FIRST_LINE, RULE_ID, Severity.ERROR, message)


def strict_type_checking(project: Project) -> list[Finding]:
    gate = fast_gate(project)
    calls = gate_calls(gate.commands if gate else ())
    names = [name for ecosystem in APPLIES for name in probed_checkers(project, ecosystem, gate, calls)]
    findings = (probe_finding(project, name, calls.get(name, [])) for name in names)
    return list(dict.fromkeys(finding for finding in findings if finding))


CHECKS = (strict_type_checking, *LINT_CHECKS, *DEAD_CODE_CHECKS, python_annotations)
