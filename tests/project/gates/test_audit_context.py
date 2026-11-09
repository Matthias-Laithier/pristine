import pytest

from tests.project.conftest import RunProject
from tests.project.quality.test_interpreted import PYPROJECT, PYTHON_MAKEFILE
from tests.project.quality.test_native import CARGO_TOML, RUST_MAKEFILE
from tests.project.quality_manifests import PYTHON_SOURCE


@pytest.mark.parametrize("config", ["database = false\n", "yanked = false\n"])
def test_cargo_config_sections_require_tables(run_project: RunProject, config: str) -> None:
    makefile = RUST_MAKEFILE.replace("check:\n", "check: audit\n").replace(
        "cargo audit", "cargo audit --no-fetch --no-yanked"
    )
    exit_code, report = run_project(
        {"Cargo.toml": CARGO_TOML, "Cargo.lock": "version = 3\n", ".cargo/audit.toml": config, "Makefile": makefile}
    )
    assert exit_code == 3
    assert report["verification_status"] == "incomplete"


def test_single_shell_recipes_do_not_certify_a_root_lockfile_after_chdir(run_project: RunProject) -> None:
    makefile = ".ONESHELL:\n" + RUST_MAKEFILE.replace("check:\n", "check: audit\n").replace(
        "cargo audit", "cd nested\n\tcargo audit --no-fetch --no-yanked"
    )
    exit_code, report = run_project(
        {"Cargo.toml": CARGO_TOML, "Cargo.lock": "version = 3\n", "nested/Cargo.toml": CARGO_TOML, "Makefile": makefile}
    )
    assert exit_code == 3
    assert report["verification_status"] == "incomplete"


@pytest.mark.parametrize("prefix, suffix", [(".IGNORE: audit\n", ""), ("", "; true")])
def test_failure_suppressing_audit_recipes_are_not_certified(run_project: RunProject, prefix: str, suffix: str) -> None:
    makefile = prefix + RUST_MAKEFILE.replace("check:\n", "check: audit\n").replace(
        "cargo audit", "cargo audit --no-fetch --no-yanked" + suffix
    )
    exit_code, report = run_project({"Cargo.toml": CARGO_TOML, "Cargo.lock": "version = 3\n", "Makefile": makefile})
    assert exit_code == 3
    assert report["verification_status"] == "incomplete"


@pytest.mark.parametrize(
    "command",
    [
        "cargo audit --no-fetch --no-yanked &",
        "cargo audit --no-fetch --no-yanked & wait",
        "-cargo audit --no-fetch --no-yanked",
        "cargo audit --no-fetch --no-yanked; true",
    ],
)
def test_complete_gate_audits_must_propagate_failures(run_project: RunProject, command: str) -> None:
    makefile = RUST_MAKEFILE.replace("check-all: check", "check-all: check audit").replace("cargo audit", command)
    exit_code, report = run_project({"Cargo.toml": CARGO_TOML, "Cargo.lock": "version = 3\n", "Makefile": makefile})
    assert exit_code == 3
    assert report["verification_status"] == "incomplete"


@pytest.mark.parametrize(
    "relay, exit_code",
    [
        ("$(MAKE) audit || true", 3),
        ("$(MAKE) audit; true", 3),
        ("true || $(MAKE) audit", 3),
        ("$(MAKE) audit", 0),
        ("$(MAKE) audit && true", 0),
    ],
)
def test_parent_audit_relays_preserve_failure_and_execution_context(
    run_project: RunProject, relay: str, exit_code: int
) -> None:
    makefile = RUST_MAKEFILE.replace("check-all: check\n", "check-all: check\n\t" + relay + "\n").replace(
        "cargo audit", "cargo audit --no-fetch --no-yanked"
    )
    result, report = run_project({"Cargo.toml": CARGO_TOML, "Cargo.lock": "version = 3\n", "Makefile": makefile})
    assert result == exit_code
    assert report["verification_status"] == ("incomplete" if exit_code else "complete")


@pytest.mark.parametrize("option, exit_code", [("-i", 3), ("-n", 3), ("-s", 0)])
def test_dead_code_relays_must_preserve_execution_and_failure(
    run_project: RunProject, option: str, exit_code: int
) -> None:
    makefile = (
        PYTHON_MAKEFILE.format(format_mode="--check").replace("\t$(RUN) vulture .\n", f"\t$(MAKE) {option} dead-code\n")
        + "dead-code:\n\tvulture .\n"
    )
    result, report = run_project({**PYTHON_SOURCE, "pyproject.toml": PYPROJECT, "Makefile": makefile})
    assert result == exit_code
    assert report["verification_status"] == ("incomplete" if exit_code else "complete")


@pytest.mark.parametrize(
    "relay, exit_code",
    [
        ("$(MAKE) -i check", 3),
        ("$(MAKE) check || true", 3),
        ("true || $(MAKE) check", 3),
        ("$(MAKE) check", 0),
        ("$(MAKE) -s check", 0),
    ],
)
def test_complete_gate_rechecks_inherited_audit_context(run_project: RunProject, relay: str, exit_code: int) -> None:
    makefile = (
        RUST_MAKEFILE.replace("check:\n", "check: audit\n")
        .replace("check-all: check\n", "check-all:\n\t" + relay + "\n")
        .replace("cargo audit", "cargo audit --no-fetch --no-yanked")
    )
    result, report = run_project({"Cargo.toml": CARGO_TOML, "Cargo.lock": "version = 3\n", "Makefile": makefile})
    assert result == exit_code
    assert report["verification_status"] == ("incomplete" if exit_code else "complete")
    assert len(report["findings"]) == (1 if exit_code else 0)


@pytest.mark.parametrize(
    "option, exit_code",
    [
        ("-i", 3),
        ("--ignore-errors", 3),
        ("-n", 3),
        ("--just-print", 3),
        ("-t", 3),
        ("-q", 3),
        ("-s", 0),
        ("--silent", 0),
    ],
)
def test_make_relay_options_must_preserve_execution_and_failure(
    run_project: RunProject, option: str, exit_code: int
) -> None:
    makefile = RUST_MAKEFILE.replace("check-all: check\n", f"check-all: check\n\t$(MAKE) {option} audit\n").replace(
        "cargo audit", "cargo audit --no-fetch --no-yanked"
    )
    result, report = run_project({"Cargo.toml": CARGO_TOML, "Cargo.lock": "version = 3\n", "Makefile": makefile})
    assert result == exit_code
    assert report["verification_status"] == ("incomplete" if exit_code else "complete")
