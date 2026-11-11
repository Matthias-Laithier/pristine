DESCRIPTION = (
    "Check predictable code structure and supported defect patterns. "
    "Use 'guide' for short judgment principles and 'checks' for exact mechanical coverage. "
    "Exit codes: 0 completed without errors, 1 findings, 2 invalid usage, 3 incomplete verification. "
    "Incomplete verification takes priority over findings."
)
GUIDE_DESCRIPTION = "Print the short implementation guide. No rulebook or compliance checklist."
CHECKS_DESCRIPTION = "List enabled check IDs, titles and detected patterns. --json prints the same metadata."
CHECK_DESCRIPTION = (
    "Check files and directories. Discovery respects git ignores and excludes generated, vendored and data files. "
    "Known grammars are downloaded on first use. Files are checked in isolated parallel workers. "
    "--max caps findings while summaries retain full counts. --json includes coverage and verification status. "
    "Deleted paths are reported as missing. Unsupported formats are listed separately. "
    "A clean scan establishes only the detected patterns listed by 'pristine checks'."
)
PROJECT_DESCRIPTION = (
    "Inspect the root Makefile, supported manifests and static-tool configurations. "
    "Check the Makefile contract, gate reachability, declared tooling and reproducible dependencies. "
    "This inspects configuration without running the project's checks. Output and exits match 'check'."
)
AUDIT_DESCRIPTION = (
    "Audit uv.lock or a directory's root uv.lock with pinned OSV-Scanner. "
    "Only native-extracted PyPI package/version advisory matches are covered. "
    "A compatible installed scanner is preferred, otherwise a verified release is cached. "
    "Online lookup requires network access. --json prints evidence and --max caps findings. "
    "Missing tools, unsupported inputs and failed scans mean incomplete verification. "
    "Advisory matches do not establish exploitability. Fixed releases are context, not upgrade recommendations."
)
