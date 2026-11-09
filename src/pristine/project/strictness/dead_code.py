from pristine.project.commands.gates import fast_gate
from pristine.project.commands.shell import program_calls
from pristine.project.commands.tool_arguments import (
    KNIP_DEAD_TYPES,
    knip_issue_types,
    option_values,
)
from pristine.project.repository.loading import Project
from pristine.project.repository.manifests import table
from pristine.project.repository.tools import TOOLS_BY_NAME, Ecosystem, Role
from pristine.project.strictness.strictness import (
    Arguments,
    Probe,
    Shortfall,
    UnverifiedConfigError,
    read_json_config,
)
from pristine.project.strictness.vulture import vulture_shortfall
from pristine.reports.findings import Finding, FindingKind, Severity

KNIP_CONFIGS = (
    "knip.json",
    "knip.jsonc",
    ".knip.json",
    ".knip.jsonc",
    "knip.ts",
    "knip.js",
    "knip.config.ts",
    "knip.config.js",
)
RULE_ID = "TL-3"
FIRST_LINE = 1


def knip_configuration(project: Project, calls: Arguments) -> tuple[str, dict[str, object]]:
    explicit = [path for arguments in calls for path in option_values(arguments, "--config", "-c")]
    if len(set(explicit)) > 1:
        raise UnverifiedConfigError("package.json", "multiple Knip configurations require review")
    path = next(iter(explicit), None) or next((path for path in KNIP_CONFIGS if path in project.entries), None)
    if path is not None:
        if not path.endswith((".json", ".jsonc")) or not project.reader.is_local_file(path):
            raise UnverifiedConfigError(path, "Knip configuration is dynamic or not a readable local JSON/JSONC file")
        return path, read_json_config(project, path)
    manifest = project.root_manifest(Ecosystem.JAVASCRIPT)
    return (manifest.path, table(manifest.settings, "knip")) if manifest else ("package.json", {})


def knip_shortfall(project: Project, calls: Arguments) -> Shortfall | None:
    path, config = knip_configuration(project, calls)
    if len(calls) != 1:
        raise UnverifiedConfigError(path, "multiple Knip invocations require review of their combined filters")
    arguments = calls[0]
    for key in ("include", "exclude"):
        values = config.get(key)
        valid = isinstance(values, list) and all(isinstance(value, str) for value in values)
        if values is not None and not valid:
            raise UnverifiedConfigError(path, f"Knip {key} must be a list of issue types")
    enabled = knip_issue_types(arguments, config)
    rules = table(config, "rules")
    if not any(kind in KNIP_DEAD_TYPES and rules.get(kind, "error") == "error" for kind in enabled):
        return Shortfall(
            path, "enable an error-level unused-file or unused-export issue type in Knip, not dependency-only reporting"
        )
    if config.get("project") == []:
        return Shortfall(path, "configure non-empty Knip project source patterns")
    if config.get("preprocessor"):
        raise UnverifiedConfigError(path, "a Knip preprocessor can change dead-code findings; review it manually")
    return None


PROBES = {"vulture": Probe("Vulture", vulture_shortfall), "knip": Probe("Knip", knip_shortfall)}


def probe_finding(project: Project, name: str, arguments: Arguments) -> Finding | None:
    if not arguments:
        return None
    try:
        shortfall = PROBES[name].check(project, arguments)
    except UnverifiedConfigError as error:
        return Finding(
            project.shown(error.path),
            FIRST_LINE,
            RULE_ID,
            Severity.WARNING,
            f"cannot verify {name} dead-code configuration: {error.reason}",
            FindingKind.VERIFICATION,
        )
    if shortfall is None:
        return None
    return Finding(
        project.shown(shortfall.path),
        FIRST_LINE,
        RULE_ID,
        Severity.ERROR,
        f"{name} does not enforce dead-code checking; {shortfall.fix}",
    )


def configured_dead_code(project: Project) -> list[Finding]:
    gate = fast_gate(project)
    if gate is None:
        return []
    calls = [
        (name, arguments) for command in gate.commands for name, arguments in program_calls(command, frozenset(PROBES))
    ]
    findings = [
        probe_finding(
            project,
            name,
            [
                arguments
                for called, arguments in calls
                if called == name and TOOLS_BY_NAME[name].checks[Role.DEAD_CODE](arguments)
            ],
        )
        for name in PROBES
    ]
    return list(dict.fromkeys(finding for finding in findings if finding))


CHECKS = (configured_dead_code,)
