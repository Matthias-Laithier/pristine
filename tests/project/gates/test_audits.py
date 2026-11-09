import json

import pytest

from tests.project.conftest import RunProject, rule_findings
from tests.project.quality.test_interpreted import PYPROJECT, PYTHON_MAKEFILE
from tests.project.quality.test_native import CARGO_TOML, RUST_MAKEFILE


@pytest.mark.parametrize("placement", ["check-all: check audit", "check-all: check"])
@pytest.mark.parametrize("command", ["pip-audit", "python -m pip_audit"])
def test_network_audit_can_run_in_complete_gate_or_independently(
    run_project: RunProject, placement: str, command: str
) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace("check-all: check", placement)
    makefile = makefile.replace("uv run pip-audit", f"uv run {command}")
    exit_code, report = run_project({"pyproject.toml": PYPROJECT, "Makefile": makefile})
    assert (exit_code, report["findings"]) == (0, [])


def test_network_audit_in_fast_gate_is_an_error(run_project: RunProject) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace(
        "check: format-check lint", "check: format-check lint audit"
    )
    exit_code, report = run_project({"pyproject.toml": PYPROJECT, "Makefile": makefile})
    assert exit_code == 1
    assert rule_findings(report, "TL-2") == [
        (
            "error",
            "make check runs the network-dependent pip-audit vulnerability audit; move it to make check-all or an identifiable regular audit target outside the fast gate",
            4,
        )
    ]
    assert report["summary"]["by_rule"] == {"TL-2": 1}


@pytest.mark.parametrize("recipe", ["echo pip-audit", "pip-audit --dry-run", "pip-audit --help"])
def test_unverified_audit_mechanism_is_a_warning_not_a_vulnerability_claim(
    run_project: RunProject, recipe: str
) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check").replace("uv run pip-audit", recipe)
    exit_code, report = run_project({"pyproject.toml": PYPROJECT, "Makefile": makefile})
    assert exit_code == 0
    assert rule_findings(report, "TL-4") == [
        (
            "warning",
            "no recognized Python dependency vulnerability audit mechanism could be verified; assess regular auditing or declare an audit command using pip-audit; network-dependent audits may run outside make check-all",
            1,
        )
    ]
    assert report["summary"]["by_rule"] == {"TL-4": 1}


@pytest.mark.parametrize("runner", ["npm", "pnpm", "bun"])
def test_native_javascript_audits_are_recognized_in_package_scripts(run_project: RunProject, runner: str) -> None:
    package = {"engines": {"node": "22"}, "scripts": {"audit": f"{runner} audit"}}
    _, report = run_project({"package.json": json.dumps(package), "Makefile": "dev:\ncheck:\ncheck-all: check\n"})
    assert rule_findings(report, "TL-4") == []


@pytest.mark.parametrize("reachable", [False, True])
def test_local_offline_audit_belongs_in_complete_gate(run_project: RunProject, reachable: bool) -> None:
    makefile = RUST_MAKEFILE.replace("cargo audit", "cargo audit --no-fetch --no-update-index --file Cargo.lock")
    if reachable:
        makefile = makefile.replace("check-all: check", "check-all: check audit")
    exit_code, report = run_project({"Cargo.toml": CARGO_TOML, "Cargo.lock": "", "Makefile": makefile})
    assert exit_code == (0 if reachable else 1)
    assert rule_findings(report, "TL-2") == (
        []
        if reachable
        else [
            (
                "error",
                "make check-all omits the deterministic local cargo vulnerability audit; include its target in make check-all",
                7,
            )
        ]
    )


def test_audit_with_local_database_configuration_is_not_asserted_network_dependent(run_project: RunProject) -> None:
    makefile = RUST_MAKEFILE.replace("check:\n", "check: audit\n")
    _, report = run_project(
        {"Cargo.toml": CARGO_TOML, "Makefile": makefile, ".cargo/audit.toml": "[database]\nfetch = false\n"}
    )
    assert rule_findings(report, "TL-2") == []
