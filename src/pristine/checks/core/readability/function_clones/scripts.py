import json
import sys
from collections import defaultdict
from dataclasses import dataclass

from pristine.reports.findings import Finding, FindingKind, Severity
from pristine.reports.outcomes import Checked
from pristine.services.isolated_inspection import inspect_in_workers

SCRIPT_SUFFIXES = frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"})
WORKER_COMMAND = (sys.executable, "-m", "pristine.checks.core.readability.function_clones.worker")


@dataclass(frozen=True)
class ScriptBody:
    path: str
    line: int
    name: str
    shape: str


def script_groups(paths: list[str]) -> tuple[list[list[ScriptBody]], list[Finding]]:
    outcomes = inspect_in_workers(paths, 1, WORKER_COMMAND)
    groups: dict[str, list[ScriptBody]] = defaultdict(list)
    failures = []
    for path, outcome in outcomes.items():
        if not isinstance(outcome, Checked):
            failures.append(Finding(path, 1, "CR-5", Severity.ERROR, outcome.reason, FindingKind.VERIFICATION))
            continue
        for record in outcome.findings:
            payload = json.loads(record.message)
            groups[payload["shape"]].append(ScriptBody(path, record.line, payload["name"], payload["shape"]))
    repeated = [sorted(group, key=lambda body: (body.path, body.line)) for group in groups.values() if len(group) > 1]
    return repeated, failures
