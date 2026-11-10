import pytest

from tests.project.conftest import RunProject
from tests.project.linting.lint_cases import ANNOTATIONS, ANNOTATIONS_MAKEFILE, PYTHON_PROJECT, annotation_findings


@pytest.mark.parametrize(
    "options",
    ["--extend-select S", "--ignore ANN401", "--select=ANN", "--isolated --select ANN"],
)
def test_ruff_cli_can_preserve_or_supply_annotation_capability(run_project: RunProject, options: str) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT + ANNOTATIONS,
        "Makefile": ANNOTATIONS_MAKEFILE.replace("ruff check .", f"ruff check {options} ."),
    }
    assert annotation_findings(files, run_project) == []


@pytest.mark.parametrize(
    "command",
    [
        "ruff check --config ruff.toml .",
        "ruff check --exclude src/legacy.py .",
        "ruff check . || true",
        "ruff check . | tee lint.log",
        "-ruff check .",
        "RUFF_OUTPUT_FORMAT=json ruff check .",
        "cd src && ruff check .",
    ],
)
def test_uncertain_annotation_gate_context_is_a_verification_gap(run_project: RunProject, command: str) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT + ANNOTATIONS,
        "Makefile": ANNOTATIONS_MAKEFILE.replace("ruff check .", command),
    }
    assert annotation_findings(files, run_project) == [("warning", "verification")]


def test_ruff_inheritance_preserves_annotation_rule_selection(run_project: RunProject) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT + '[tool.ruff]\nextend = "config/base.toml"\n',
        "config/base.toml": '[lint]\nextend-select = ["ANN", "S", "ASYNC", "DTZ", "G", "T20", "FBT", "BLE", "ARG", "ERA"]\n',
        "Makefile": ANNOTATIONS_MAKEFILE,
    }
    assert annotation_findings(files, run_project) == []


def test_ruff_extended_per_file_ignores_cannot_erase_a_disable(run_project: RunProject) -> None:
    config = ANNOTATIONS + 'per-file-ignores = {"*" = ["ANN"]}\nextend-per-file-ignores = {"*" = ["S101"]}\n'
    files = {"pyproject.toml": PYTHON_PROJECT + config, "Makefile": ANNOTATIONS_MAKEFILE}
    assert annotation_findings(files, run_project) == [("error", "rule")]


@pytest.mark.parametrize("config", ["mypy.ini", ".mypy.ini", "setup.cfg"])
def test_mypy_ini_module_annotation_override_is_a_verification_gap(run_project: RunProject, config: str) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT,
        "Makefile": ANNOTATIONS_MAKEFILE.replace("ty check", "mypy --strict"),
        config: "[mypy]\nstrict = True\n[mypy-legacy.*]\ndisallow_untyped_defs = False\n",
    }
    assert annotation_findings(files, run_project) == [("warning", "verification")]


def test_mypy_reenabling_annotation_error_code_restores_capability(run_project: RunProject) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT,
        "Makefile": ANNOTATIONS_MAKEFILE.replace(
            "ty check", "mypy --strict --disable-error-code=no-untyped-def --enable-error-code=no-untyped-def"
        ),
    }
    assert annotation_findings(files, run_project) == []


def test_mypy_cli_disables_accumulate_with_configuration(run_project: RunProject) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT + '[tool.mypy]\nstrict = true\ndisable_error_code = ["no-untyped-def"]\n',
        "Makefile": ANNOTATIONS_MAKEFILE.replace("ty check", "mypy --strict --disable-error-code arg-type"),
    }
    assert annotation_findings(files, run_project) == [("error", "rule")]


def test_mypy_cli_strict_overrides_global_untyped_definition_setting(run_project: RunProject) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT + "[tool.mypy]\ndisallow_untyped_defs = false\n",
        "Makefile": ANNOTATIONS_MAKEFILE.replace("ty check", "mypy --strict"),
    }
    assert annotation_findings(files, run_project) == []
