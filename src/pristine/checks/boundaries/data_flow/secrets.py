from pristine.checks.definitions import PathCheck
from pristine.reports.findings import Finding, FindingKind, Severity
lazy from pristine.services.gitleaks import Leak, SecretScanFailed, scan_paths

CHECK_ID = "SAFE-2"
SCAN_SCOPE_PATH = "."
SCAN_SCOPE_LINE = 0


def leak_finding(leak: Leak) -> Finding:
    message = (
        f"gitleaks rule '{leak.scanner_rule_id}' matched a secret; load it from the environment or a secret provider, "
        "and rotate it if it was ever committed"
    )
    return Finding(leak.path, leak.line, CHECK_ID, Severity.ERROR, message)


def check_secrets(paths: list[str]) -> list[Finding]:
    try:
        leaks = scan_paths(paths)
    except SecretScanFailed as error:
        message = f"secret scan did not run: {error}; install gitleaks or fix the failure, then rerun"
        return [
            Finding(
                SCAN_SCOPE_PATH,
                SCAN_SCOPE_LINE,
                CHECK_ID,
                Severity.WARNING,
                message,
                FindingKind.VERIFICATION,
            )
        ]
    return [leak_finding(leak) for leak in leaks]


CHECK = PathCheck(
    check_id=CHECK_ID,
    title="Secrets",
    summary=(
        "Secrets in every discovered file, skipped data and lockfiles included, detected by gitleaks with its "
        "default rules or the project's .gitleaks.toml; a failed scan is an incomplete-verification finding."
    ),
    run=check_secrets,
)
