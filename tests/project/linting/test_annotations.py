import pytest

from tests.project.conftest import RunProject
from tests.project.linting.lint_cases import ANNOTATIONS, PYTHON_PROJECT, annotation_findings, with_python_lint_config
from tests.project.linting.lint_cases import ANNOTATIONS_MAKEFILE as MAKEFILE


@pytest.mark.parametrize("checker", ["ty", "pyrefly", "pyright", "basedpyright"])
def test_inference_alone_does_not_enforce_annotations(run_project: RunProject, checker: str) -> None:
    files = with_python_lint_config('[tool.ruff.lint]\nselect = ["ALL"]\nignore = ["ANN"]\n')
    files["Makefile"] = MAKEFILE.replace("ty check", f"{checker} check")
    assert annotation_findings(files, run_project) == [("error", "rule")]


@pytest.mark.parametrize(
    "config",
    [
        ANNOTATIONS,
        '[tool.ruff.lint]\nselect = ["ALL"]\nignore = ["ANN401"]\n',
        '[tool.ruff.lint]\nselect = ["ANN001", "ANN002", "ANN003", "ANN201", "ANN202", "ANN204", "ANN205", "ANN206"]\nignore = ["ANN"]\n',
    ],
)
def test_ruff_can_enforce_annotations_without_any_type_rule(run_project: RunProject, config: str) -> None:
    files = {"pyproject.toml": PYTHON_PROJECT + config, "Makefile": MAKEFILE}
    assert annotation_findings(files, run_project) == []


@pytest.mark.parametrize(
    "extra",
    [
        *[
            f'ignore = ["{code}"]\n'
            for code in ("ANN001", "ANN002", "ANN003", "ANN201", "ANN202", "ANN204", "ANN205", "ANN206")
        ],
        'per-file-ignores = {"*" = ["ANN"]}\n',
        "[tool.ruff.lint.flake8-annotations]\nignore-fully-untyped = true\n",
        "[tool.ruff.lint.flake8-annotations]\nsuppress-dummy-args = true\n",
        "[tool.ruff.lint.flake8-annotations]\nsuppress-none-returning = true\n",
        "[tool.ruff.lint.flake8-annotations]\nmypy-init-return = true\n",
    ],
)
def test_ruff_annotation_disables_are_not_certified(run_project: RunProject, extra: str) -> None:
    files = {"pyproject.toml": PYTHON_PROJECT + ANNOTATIONS + extra, "Makefile": MAKEFILE}
    assert annotation_findings(files, run_project) == [("error", "rule")]


@pytest.mark.parametrize("options", ["--ignore ANN", "--select S", "--isolated", "--exit-zero", "--fix-only"])
def test_ruff_gate_overrides_are_not_certified(run_project: RunProject, options: str) -> None:
    files = {
        "pyproject.toml": PYTHON_PROJECT + ANNOTATIONS,
        "Makefile": MAKEFILE.replace("ruff check .", f"ruff check {options} ."),
    }
    assert annotation_findings(files, run_project) == [("error", "rule")]


@pytest.mark.parametrize(
    "extra",
    [
        'per-file-ignores = {"src/legacy.py" = ["ANN"]}\n',
        '[tool.ruff]\nexclude = ["src/legacy.py"]\n',
    ],
)
def test_partial_annotation_exclusions_are_verification_gaps(run_project: RunProject, extra: str) -> None:
    files = {"pyproject.toml": PYTHON_PROJECT + ANNOTATIONS + extra, "Makefile": MAKEFILE}
    assert annotation_findings(files, run_project) == [("warning", "verification")]


def test_missing_gate_annotation_capability_is_reported(run_project: RunProject) -> None:
    files = {"pyproject.toml": PYTHON_PROJECT + ANNOTATIONS, "Makefile": MAKEFILE.replace("\truff check .\n", "")}
    assert annotation_findings(files, run_project) == [("error", "rule")]


def test_strict_mypy_is_an_annotation_capability_without_ruff_ann(run_project: RunProject) -> None:
    files = with_python_lint_config('[tool.ruff.lint]\nselect = ["ALL"]\nignore = ["ANN"]\n')
    assert annotation_findings(files, run_project) == []


@pytest.mark.parametrize(
    "options",
    ["--allow-untyped-defs", "--disable-error-code no-untyped-def", "--config-file missing.ini"],
)
def test_mypy_strict_overrides_are_not_certified(run_project: RunProject, options: str) -> None:
    files = with_python_lint_config('[tool.ruff.lint]\nselect = ["ALL"]\nignore = ["ANN"]\n')
    files["Makefile"] = files["Makefile"].replace("mypy --strict", f"mypy --strict {options}")
    expected = "warning" if "config-file" in options else "error"
    assert annotation_findings(files, run_project) == [(expected, "verification" if expected == "warning" else "rule")]


@pytest.mark.parametrize(
    "settings",
    [
        "[tool.mypy]\nstrict = true\ndisallow_untyped_defs = false\n",
        "[tool.mypy]\nstrict = true\nignore_errors = true\n",
        '[tool.mypy]\nstrict = true\n[[tool.mypy.overrides]]\nmodule = "legacy.*"\ndisallow_untyped_defs = false\n',
    ],
)
def test_mypy_module_and_global_disables_are_not_certified(run_project: RunProject, settings: str) -> None:
    files = with_python_lint_config('[tool.ruff.lint]\nselect = ["ALL"]\nignore = ["ANN"]\n' + settings)
    files["Makefile"] = files["Makefile"].replace("mypy --strict", "mypy")
    expected = "warning" if "overrides" in settings else "error"
    assert annotation_findings(files, run_project) == [(expected, "verification" if expected == "warning" else "rule")]
