from dataclasses import dataclass

from pristine.project.commands.gates import Invocation, fast_gate, invocations
from pristine.project.repository.loading import Project
from pristine.project.repository.makefile import COMPLETE_GATE, FAST_GATE, reach
from pristine.project.repository.tools import Ecosystem, Role
from pristine.reports.findings import Finding, Severity

RULE_ID = "TL-2"
FIRST_LINE = 1


@dataclass(frozen=True)
class DeclaredChecks:
    path: str
    line: int
    source: str
    invocations: frozenset[Invocation]


def complete_gate_runs_fast_gate(project: Project) -> list[Finding]:
    makefile = project.makefile
    if makefile is None or COMPLETE_GATE not in makefile.rules or FAST_GATE not in makefile.rules:
        return []
    if FAST_GATE in reach(makefile, COMPLETE_GATE).targets:
        return []
    rule = makefile.rules[COMPLETE_GATE]
    message = (
        f"'{COMPLETE_GATE}' does not run '{FAST_GATE}'; list it as a prerequisite "
        f"('{COMPLETE_GATE}: {FAST_GATE} ...') or call '$(MAKE) {FAST_GATE}' in its recipe"
    )
    return [Finding(project.shown(rule.path), rule.line, RULE_ID, Severity.ERROR, message)]


def package_scripts(project: Project) -> dict[str, str]:
    manifest = project.root_manifest(Ecosystem.JAVASCRIPT)
    return dict(manifest.scripts) if manifest else {}


def declared_checks(project: Project) -> list[DeclaredChecks]:
    makefile = project.makefile
    if makefile is None:
        return []
    scripts = package_scripts(project)
    targets = (
        DeclaredChecks(
            project.shown(rule.path),
            rule.line,
            f"Makefile target '{name}'",
            invocations(makefile.expand(line) for line in rule.recipe),
        )
        for name, rule in makefile.rules.items()
    )
    manifest = project.root_manifest(Ecosystem.JAVASCRIPT)
    if manifest is None:
        return [checks for checks in targets if checks.invocations]
    script_checks = (
        DeclaredChecks(
            project.shown(manifest.path),
            FIRST_LINE,
            f"package script '{name}'",
            invocations((body,)),
        )
        for name, body in scripts.items()
    )
    return [checks for checks in [*targets, *script_checks] if checks.invocations]


def omitted_checks(project: Project) -> list[Finding]:
    gate = fast_gate(project)
    if gate is None:
        return []
    findings = [
        Finding(
            declared.path,
            declared.line,
            RULE_ID,
            Severity.ERROR,
            f"make check does not run the configured {name} {role} declared in {declared.source}",
        )
        for declared in declared_checks(project)
        for name, role in sorted(declared.invocations - gate.invocations, key=lambda item: (item[0], item[1].value))
        if role is not Role.VULNERABILITY_AUDIT
    ]
    return findings


CHECKS = (complete_gate_runs_fast_gate, omitted_checks)
