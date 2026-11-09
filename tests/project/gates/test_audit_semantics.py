import pytest

from tests.project.conftest import RunProject, rule_findings
from tests.project.quality.test_interpreted import PYPROJECT, PYTHON_MAKEFILE
from tests.project.quality.test_native import CARGO_TOML, GO_MAKEFILE, GO_MOD, RUST_MAKEFILE


@pytest.mark.parametrize(
    "files, makefile, command, tool",
    [
        (
            {"pyproject.toml": PYPROJECT, "src/invoices.py": "sum([1, 2])\n"},
            PYTHON_MAKEFILE.format(format_mode="--check"),
            "pip-audit --cache-dir .audit-cache",
            "pip-audit",
        ),
        ({"go.mod": GO_MOD}, GO_MAKEFILE, "govulncheck -json ./...", "govulncheck"),
        ({"go.mod": GO_MOD}, GO_MAKEFILE, "govulncheck -format sarif ./...", "govulncheck"),
        ({"go.mod": GO_MOD}, GO_MAKEFILE, "govulncheck -format openvex ./...", "govulncheck"),
        ({"go.mod": GO_MOD}, GO_MAKEFILE, "govulncheck -db=https://vuln.go.dev ./...", "govulncheck"),
        ({"Cargo.toml": CARGO_TOML, ".cargo/audit.toml": ""}, RUST_MAKEFILE, "cargo audit", "cargo"),
        (
            {"Cargo.toml": CARGO_TOML, ".cargo/audit.toml": "[database]\nfetch = true\n"},
            RUST_MAKEFILE,
            "cargo audit --db .advisory-cache",
            "cargo",
        ),
    ],
)
def test_transport_settings_and_reporting_do_not_make_fast_audits_offline(
    run_project: RunProject, files: dict[str, str], makefile: str, command: str, tool: str
) -> None:
    replacement = {"pip-audit": "uv run pip-audit", "govulncheck": "govulncheck ./...", "cargo": "cargo audit"}[tool]
    makefile = makefile.replace(replacement, command).replace("check:", "check: audit", 1)
    exit_code, report = run_project({**files, "Makefile": makefile})
    assert exit_code == 1
    assert [message for _, message, _ in rule_findings(report, "TL-2")] == [
        f"make check runs the network-dependent {tool} vulnerability audit; move it to make check-all or an identifiable regular audit target outside the fast gate"
    ]


@pytest.mark.parametrize("command", ["pip-audit --cache-dir .audit-cache", "pip-audit --format json"])
def test_cache_and_reporting_are_valid_in_regular_audit_targets(run_project: RunProject, command: str) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace("uv run pip-audit", command)
    exit_code, report = run_project(
        {"pyproject.toml": PYPROJECT, "src/invoices.py": "sum([1, 2])\n", "Makefile": makefile}
    )
    assert (exit_code, report["findings"]) == (0, [])


@pytest.mark.parametrize(
    "command",
    ["cargo audit --no-fetch", "cargo audit --no-update-index", "cargo audit --db .local --no-fetch --no-yanked"],
)
def test_unproven_local_audits_are_verification_gaps(run_project: RunProject, command: str) -> None:
    makefile = RUST_MAKEFILE.replace("check:\n", "check: audit\n").replace("cargo audit", command)
    exit_code, report = run_project({"Cargo.toml": CARGO_TOML, "Makefile": makefile})
    assert exit_code == 3
    assert rule_findings(report, "TL-2") == [
        (
            "warning",
            "cannot verify cargo audit is offline and fail-closed in make check; review database, dependency resolution and command context or move the audit outside the fast gate",
            3,
        )
    ]


@pytest.mark.parametrize("complete", [False, True])
def test_govulncheck_reports_are_valid_regular_audits_but_not_closed_gates(
    run_project: RunProject, complete: bool
) -> None:
    makefile = GO_MAKEFILE.replace("govulncheck ./...", "govulncheck -json ./...")
    if complete:
        makefile = makefile.replace("check-all: check", "check-all: check audit")
    exit_code, report = run_project({"go.mod": GO_MOD, "Makefile": makefile})
    assert exit_code == (3 if complete else 0)
    assert rule_findings(report, "TL-2") == (
        [
            (
                "warning",
                "cannot verify govulncheck vulnerability enforcement in make check-all; structured reports exit successfully even with vulnerabilities, so verify a fail-closed consumer or use text output",
                7,
            )
        ]
        if complete
        else []
    )


@pytest.mark.parametrize("command", ["govulncheck -format text ./...", "govulncheck -json=false -format text ./..."])
def test_govulncheck_text_reporting_remains_an_enforcing_complete_gate(run_project: RunProject, command: str) -> None:
    makefile = GO_MAKEFILE.replace("govulncheck ./...", command).replace("check-all: check", "check-all: check audit")
    exit_code, report = run_project({"go.mod": GO_MOD, "Makefile": makefile})
    assert (exit_code, report["findings"]) == (0, [])


@pytest.mark.parametrize("fast", [False, True])
def test_local_go_database_declarations_do_not_prove_offline_dependency_resolution(
    run_project: RunProject, fast: bool
) -> None:
    makefile = GO_MAKEFILE.replace("govulncheck ./...", "govulncheck -db file:///local-vulnerability-db ./...")
    if fast:
        makefile = makefile.replace("check:\n", "check: audit\n")
    exit_code, report = run_project({"go.mod": GO_MOD, "Makefile": makefile})
    assert exit_code == (3 if fast else 0)
    assert len(rule_findings(report, "TL-2")) == (1 if fast else 0)


def test_invalid_cargo_configuration_is_not_silently_certified(run_project: RunProject) -> None:
    makefile = RUST_MAKEFILE.replace("check:\n", "check: audit\n")
    exit_code, report = run_project(
        {"Cargo.toml": CARGO_TOML, "Makefile": makefile, ".cargo/audit.toml": "[database\n"}
    )
    assert exit_code == 3
    assert report["verification_status"] == "incomplete"
    assert report["unchecked"][0]["reason"].startswith("Cargo audit configuration is invalid TOML")


def test_cargo_cannot_borrow_a_lockfile_from_a_different_working_directory(run_project: RunProject) -> None:
    makefile = RUST_MAKEFILE.replace("check:\n", "check: audit\n").replace(
        "cargo audit", "cd nested && cargo audit --no-fetch --no-yanked"
    )
    exit_code, report = run_project(
        {"Cargo.toml": CARGO_TOML, "Cargo.lock": "version = 3\n", "nested/Cargo.toml": CARGO_TOML, "Makefile": makefile}
    )
    assert exit_code == 3
    assert rule_findings(report, "TL-2") == [
        (
            "warning",
            "cannot verify cargo audit is offline and fail-closed in make check; review database, dependency resolution and command context or move the audit outside the fast gate",
            3,
        )
    ]


def test_submake_in_a_changed_directory_does_not_expand_root_audit_targets(run_project: RunProject) -> None:
    makefile = RUST_MAKEFILE.replace("\tcargo check\n", "\tcargo check\n\tcd nested && $(MAKE) audit\n").replace(
        "cargo audit", "cargo audit --no-fetch --no-yanked"
    )
    exit_code, report = run_project(
        {"Cargo.toml": CARGO_TOML, "Cargo.lock": "version = 3\n", "nested/Cargo.toml": CARGO_TOML, "Makefile": makefile}
    )
    assert exit_code == 3
    assert report["verification_status"] == "incomplete"
