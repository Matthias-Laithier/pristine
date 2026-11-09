from pristine.project.commands.gates import Gate, fast_gate, quality_gate, verifiable_context
from pristine.project.commands.shell import program_calls
from pristine.project.commands.tool_arguments import govulncheck_report_only
from pristine.project.repository.loading import Project
from pristine.project.repository.makefile import COMPLETE_GATE
from pristine.project.repository.tools import TOOLS_BY_NAME, Role
from pristine.reports.findings import Finding, FindingKind, Severity

AUDIT_NAMES = frozenset(name for name, tool in TOOLS_BY_NAME.items() if Role.VULNERABILITY_AUDIT in tool.checks)


def complete_finding(project: Project, gate: Gate, name: str, command: str, arguments: list[str]) -> Finding | None:
    if not verifiable_context(project, gate, command):
        message = f"cannot verify {name} vulnerability enforcement in make check-all; audit recipe suppresses failures or has unverified shell or working-directory context"
    elif name == "govulncheck" and govulncheck_report_only(arguments):
        message = "cannot verify govulncheck vulnerability enforcement in make check-all; structured reports exit successfully even with vulnerabilities, so verify a fail-closed consumer or use text output"
    else:
        return None
    return Finding(
        project.shown(gate.rule.path), gate.rule.line, "TL-2", Severity.WARNING, message, FindingKind.VERIFICATION
    )


def complete_audit_enforcement(project: Project) -> list[Finding]:
    gate = quality_gate(project, COMPLETE_GATE)
    if gate is None:
        return []
    fast = fast_gate(project)
    already_checked = set(fast.commands) if fast else set()
    findings = [
        complete_finding(project, gate, name, command, arguments)
        for command in gate.commands
        if command not in already_checked
        or (fast and verifiable_context(project, fast, command) and not verifiable_context(project, gate, command))
        for name, arguments in program_calls(command, AUDIT_NAMES)
        if TOOLS_BY_NAME[name].checks[Role.VULNERABILITY_AUDIT](arguments)
    ]
    return list(dict.fromkeys(finding for finding in findings if finding))


CHECKS = (complete_audit_enforcement,)
