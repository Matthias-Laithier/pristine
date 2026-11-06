from pristine.project.repository.loading import Project
from pristine.project.repository.makefile import COMPLETE_GATE, FAST_GATE, reach
from pristine.reports.findings import Finding, Severity

RULE_ID = "TL-2"


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


CHECKS = (complete_gate_runs_fast_gate,)
