from pristine.project.commands.gates import fast_gate, verifiable_context
from pristine.project.commands.scripts import with_package_scripts
from pristine.project.commands.shell import program_calls, root_working_directory, verifiable_command
from pristine.project.gates.audit_network import AuditNetwork, network_audit
from pristine.project.gates.contract import declared_checks, package_scripts
from pristine.project.repository.loading import Project
from pristine.project.repository.makefile import COMPLETE_GATE, reach
from pristine.project.repository.tools import TOOLS_BY_NAME, Ecosystem, Role
from pristine.reports.findings import Finding, FindingKind, Severity

FIRST_LINE = 1
AUDIT_NAMES = frozenset(name for name, tool in TOOLS_BY_NAME.items() if Role.VULNERABILITY_AUDIT in tool.checks)


def recognizable_audits(project: Project) -> list[Finding]:
    if project.makefile is None:
        return []
    declared = {invocation for checks in declared_checks(project) for invocation in checks.invocations}
    findings = []
    for ecosystem in Ecosystem:
        manifest = project.root_manifest(ecosystem)
        if manifest is None:
            continue
        candidates = [name for name in AUDIT_NAMES if TOOLS_BY_NAME[name].ecosystem is ecosystem]
        runs_audit = any((name, Role.VULNERABILITY_AUDIT) in declared for name in candidates)
        if runs_audit:
            continue
        message = (
            f"no recognized {ecosystem} dependency vulnerability audit mechanism could be verified; "
            f"assess regular auditing or declare an audit command using {', '.join(sorted(candidates))}; "
            "network-dependent audits may run outside make check-all"
        )
        findings.append(Finding(project.shown(manifest.path), FIRST_LINE, "TL-4", Severity.WARNING, message))
    return findings


def fast_audit_finding(project: Project, name: str, command: str, arguments: list[str]) -> Finding | None:
    gate = fast_gate(project)
    if gate is None:
        return None
    network = (
        network_audit(project, name, arguments)
        if verifiable_context(project, gate, command)
        else AuditNetwork.UNVERIFIED
    )
    if network is AuditNetwork.LOCAL:
        return None
    if network is AuditNetwork.NETWORK:
        message = f"make check runs the network-dependent {name} vulnerability audit; move it to make check-all or an identifiable regular audit target outside the fast gate"
        return Finding(project.shown(gate.rule.path), gate.rule.line, "TL-2", Severity.ERROR, message)
    message = f"cannot verify {name} audit is offline and fail-closed in make check; review database, dependency resolution and command context or move the audit outside the fast gate"
    return Finding(
        project.shown(gate.rule.path), gate.rule.line, "TL-2", Severity.WARNING, message, FindingKind.VERIFICATION
    )


def network_audits_in_fast_gate(project: Project) -> list[Finding]:
    gate = fast_gate(project)
    if gate is None:
        return []
    findings = [
        fast_audit_finding(project, name, command, arguments)
        for command in gate.commands
        for name, arguments in program_calls(command, AUDIT_NAMES)
        if TOOLS_BY_NAME[name].checks[Role.VULNERABILITY_AUDIT](arguments)
    ]
    return list(dict.fromkeys(finding for finding in findings if finding))


def missing_deterministic_audits(project: Project) -> list[str]:
    makefile = project.makefile
    if (
        makefile is None
        or makefile.has_conditionals
        or makefile.unverified_recipes
        or COMPLETE_GATE not in makefile.rules
    ):
        return []
    scripts = package_scripts(project)
    complete = with_package_scripts(reach(makefile, COMPLETE_GATE).commands, scripts)
    reached = {
        (name, tuple(arguments)) for command in complete for name, arguments in program_calls(command, AUDIT_NAMES)
    }
    declared = [makefile.expand(line) for rule in makefile.rules.values() for line in rule.recipe] + list(
        scripts.values()
    )
    return sorted(
        {
            name
            for command in declared
            if verifiable_command(command) and root_working_directory(command)
            for name, arguments in program_calls(command, AUDIT_NAMES)
            if TOOLS_BY_NAME[name].checks[Role.VULNERABILITY_AUDIT](arguments)
            and network_audit(project, name, arguments) is AuditNetwork.LOCAL
            and (name, tuple(arguments)) not in reached
        }
    )


def omitted_deterministic_audits(project: Project) -> list[Finding]:
    makefile = project.makefile
    if makefile is None or COMPLETE_GATE not in makefile.rules:
        return []
    rule = makefile.rules[COMPLETE_GATE]
    return [
        Finding(
            project.shown(rule.path),
            rule.line,
            "TL-2",
            Severity.ERROR,
            f"make check-all omits the deterministic local {name} vulnerability audit; "
            "include its target in make check-all",
        )
        for name in missing_deterministic_audits(project)
    ]


CHECKS = (
    recognizable_audits,
    network_audits_in_fast_gate,
    omitted_deterministic_audits,
)
