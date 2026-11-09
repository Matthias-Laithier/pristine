from pristine.project.commands.gates import fast_gate
from pristine.project.commands.scripts import with_package_scripts
from pristine.project.commands.shell import program_calls, verifiable_command
from pristine.project.commands.tool_arguments import option, option_values
from pristine.project.gates.contract import declared_checks, package_scripts
from pristine.project.repository.loading import Project
from pristine.project.repository.makefile import COMPLETE_GATE, reach
from pristine.project.repository.tools import TOOLS_BY_NAME, Ecosystem, Role
from pristine.reports.findings import Finding, Severity

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


def network_audit(project: Project, name: str, arguments: list[str]) -> bool:
    if option("--offline", "--no-fetch", "--no-update-index", "-db", "--db", "--cache-dir")(arguments):
        return False
    if name == "cargo" and project.reader.is_local_file(".cargo/audit.toml"):
        return False
    return name != "govulncheck" or not option("-mode", "-json", "-format")(arguments)


def network_audits_in_fast_gate(project: Project) -> list[Finding]:
    gate = fast_gate(project)
    if gate is None or (project.makefile and project.makefile.has_conditionals):
        return []
    calls = (
        (name, arguments)
        for command in gate.commands
        if verifiable_command(command)
        for name, arguments in program_calls(command, AUDIT_NAMES)
    )
    names = sorted(
        {
            name
            for name, arguments in calls
            if TOOLS_BY_NAME[name].checks[Role.VULNERABILITY_AUDIT](arguments)
            and network_audit(project, name, arguments)
        }
    )
    return [
        Finding(
            project.shown(gate.rule.path),
            gate.rule.line,
            "TL-2",
            Severity.ERROR,
            f"make check runs the network-dependent {name} vulnerability audit; "
            "move it to make check-all or an identifiable regular audit target outside the fast gate",
        )
        for name in names
    ]


def deterministic_audit(project: Project, name: str, arguments: list[str]) -> bool:
    paths = option_values(arguments, "--file", "-f")
    return (
        name == "cargo"
        and {"--no-fetch", "--no-update-index"}.issubset(arguments)
        and len(paths) == 1
        and project.reader.is_local_file(paths[0])
    )


def missing_deterministic_audits(project: Project) -> list[str]:
    makefile = project.makefile
    if makefile is None or makefile.has_conditionals or COMPLETE_GATE not in makefile.rules:
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
            if verifiable_command(command)
            for name, arguments in program_calls(command, AUDIT_NAMES)
            if TOOLS_BY_NAME[name].checks[Role.VULNERABILITY_AUDIT](arguments)
            and deterministic_audit(project, name, arguments)
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


CHECKS = (recognizable_audits, network_audits_in_fast_gate, omitted_deterministic_audits)
