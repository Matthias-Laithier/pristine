from pathlib import Path

from pristine.cli.main import main
from tests.project.conftest import RunProject, rule_findings

CONTRACT = "dev:\n\t./run\ncheck:\n\tpytest\ncheck-all: check\n"


def test_missing_makefile_is_an_error(run_project: RunProject) -> None:
    exit_code, report = run_project({"README.md": "readme\n"})
    assert exit_code == 1
    assert [message for _, message, _ in rule_findings(report, "TL-1")] == [
        "no Makefile at the repository root; add one with the dev, check, and check-all targets"
    ]


def test_targets_come_from_rule_lines_only(run_project: RunProject) -> None:
    makefile = (
        "APP := app\n"
        ".PHONY: dev check check-all\n"
        "dev check: install ## both targets\n"
        "\tcheck-all: not a rule, a recipe line\n"
        "check-all ?= assignment\n"
        "install: export MODE = fast\n"
        "define SNIPPET\n"
        "check-all:\n"
        "endef\n"
    )
    _, report = run_project({"Makefile": makefile})
    assert rule_findings(report, "TL-1") == [("error", "the Makefile has no 'check-all' target", 1)]


def test_local_includes_define_targets(run_project: RunProject) -> None:
    _, report = run_project(
        {"Makefile": "include rules/contract.mk\n-include missing.mk\n", "rules/contract.mk": CONTRACT}
    )
    assert rule_findings(report, "TL-1") == []


def test_check_all_must_run_check(run_project: RunProject) -> None:
    makefile = "dev:\n\t./run\ncheck:\n\tpytest\n\ncheck-all: slow\n\tpytest -m slow\nslow:\n\t$(MAKE) -C web check\n"
    _, report = run_project({"Makefile": makefile})
    assert [(severity, line) for severity, _, line in rule_findings(report, "TL-2")] == [("error", 6)]


def test_check_all_may_reach_check_through_a_sub_make(run_project: RunProject) -> None:
    makefile = (
        "dev:\n\t./run\ncheck:\n\tpytest\ncheck-all: ci\nci:\n\t@$(MAKE) --no-print-directory check && pytest -m slow\n"
    )
    _, report = run_project({"Makefile": makefile})
    assert rule_findings(report, "TL-2") == []


def test_artifacts_and_component_makefiles_are_warnings(run_project: RunProject) -> None:
    files = {
        "Makefile": CONTRACT,
        "deploy/Dockerfile.api": "FROM python\n",
        "web/Makefile": CONTRACT,
        "node_modules/tool/Makefile": CONTRACT,
        "copier/template/Makefile": CONTRACT,
    }
    exit_code, report = run_project(files)
    assert exit_code == 0
    assert rule_findings(report, "TL-1") == [
        (
            "warning",
            "the project produces artifacts (container build file deploy/Dockerfile.api) but the Makefile has no 'build' target",
            1,
        ),
        ("warning", "component Makefiles found (web/Makefile); keep one Makefile at the repository root", 1),
    ]


def test_path_must_be_a_directory(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text(CONTRACT)
    assert main(["project", str(tmp_path / "Makefile")]) == 2
