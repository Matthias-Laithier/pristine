from pristine.checks.registry import PathCheck, register_path_check
from pristine.reports.findings import Finding, FindingKind, Severity
lazy from pristine.services.gitleaks import Leak, SecretScanFailed, scan_paths

RULE_ID = "BS-2"
SCAN_SCOPE_PATH = "."
SCAN_SCOPE_LINE = 0


def leak_finding(leak: Leak) -> Finding:
    message = (
        f"gitleaks rule '{leak.rule_id}' matched a secret; load it from the environment or a secret provider, "
        "and rotate it if it was ever committed"
    )
    return Finding(leak.path, leak.line, RULE_ID, Severity.ERROR, message)


def check_secrets(paths: list[str]) -> list[Finding]:
    try:
        leaks = scan_paths(paths)
    except SecretScanFailed as error:
        message = f"secret scan did not run: {error}; install gitleaks or fix the failure, then rerun"
        return [
            Finding(
                SCAN_SCOPE_PATH,
                SCAN_SCOPE_LINE,
                RULE_ID,
                Severity.WARNING,
                message,
                FindingKind.VERIFICATION,
            )
        ]
    return [leak_finding(leak) for leak in leaks]


register_path_check(
    PathCheck(
        rule_id=RULE_ID,
        summary=(
            "Secrets in every discovered file, skipped data and lockfiles included, detected by gitleaks with its "
            "default rules or the project's .gitleaks.toml; a scan that cannot run is reported as a warning."
        ),
        run=check_secrets,
    )
)
