import pytest

from tests.project.conftest import RunProject
from tests.project.quality.test_interpreted import PYPROJECT, PYTHON_MAKEFILE
from tests.project.quality_manifests import PYTHON_SOURCE

ANNOTATION_SOURCE = {"src/invoices.py": "def send_invoice(invoice):\n    return invoice\n"}


@pytest.mark.parametrize("option, exit_code", [("-i", 3), ("-n", 3), ("-s", 0)])
def test_inherited_annotation_context_preserves_both_tooling_capabilities(
    run_project: RunProject, option: str, exit_code: int
) -> None:
    makefile = (
        PYTHON_MAKEFILE.format(format_mode="--check").replace(
            "\t$(RUN) mypy --strict .\n", f"\t$(MAKE) {option} annotations\n"
        )
        + "annotations:\n\tmypy --strict .\n"
    )
    result, report = run_project({**PYTHON_SOURCE, "pyproject.toml": PYPROJECT, "Makefile": makefile})
    assert result == exit_code
    assert report["verification_status"] == ("incomplete" if exit_code else "complete")
    assert report["summary"]["verification_failures"] == (2 if exit_code else 0)


@pytest.mark.parametrize(
    "mode, options, exit_code",
    [
        ("fix-only = true", "", 3),
        ("fix-only = false", "", 0),
        ("fix-only = true", "--no-fix-only", 0),
        ("fix = true", "", 3),
        ("fix = true", "--no-fix", 0),
    ],
)
def test_ruff_annotation_configuration_modes_match_command_enforcement(
    run_project: RunProject, mode: str, options: str, exit_code: int
) -> None:
    configuration = PYPROJECT.replace('"T20"]', '"T20", "ANN"]').replace(
        "[tool.ruff.lint]", f"[tool.ruff]\n{mode}\n[tool.ruff.lint]"
    )
    configuration += '[tool.ty.rules]\nall = "error"\n'
    makefile = (
        PYTHON_MAKEFILE.format(format_mode="--check")
        .replace("mypy --strict .", "ty check .")
        .replace("cd app && ", "")
        .replace("ruff check .", f"ruff check {options} .")
    )
    result, report = run_project({**ANNOTATION_SOURCE, "pyproject.toml": configuration, "Makefile": makefile})
    assert result == exit_code
    assert report["verification_status"] == ("incomplete" if exit_code else "complete")


@pytest.mark.parametrize("name", ["src/.ruff.toml", "src/ruff.toml"])
def test_nearer_ruff_annotation_configuration_is_checked_even_when_hidden(run_project: RunProject, name: str) -> None:
    configuration = PYPROJECT.replace('"T20"]', '"T20", "ANN"]') + '[tool.ty.rules]\nall = "error"\n'
    makefile = (
        PYTHON_MAKEFILE.format(format_mode="--check").replace("mypy --strict .", "ty check .").replace("cd app && ", "")
    )
    result, report = run_project(
        {**ANNOTATION_SOURCE, "pyproject.toml": configuration, "Makefile": makefile, name: '[lint]\nselect = ["F"]\n'}
    )
    assert result == 3
    assert report["verification_status"] == "incomplete"


def test_unreached_ignored_recipe_cannot_disable_active_annotation_enforcement(run_project: RunProject) -> None:
    makefile = PYTHON_MAKEFILE.format(format_mode="--check") + "diagnose:\n\t-$(RUN) mypy --strict .\n"
    result, report = run_project({**PYTHON_SOURCE, "pyproject.toml": PYPROJECT, "Makefile": makefile})
    assert (result, report["findings"]) == (0, [])


@pytest.mark.parametrize(
    "setting, exit_code",
    [
        ('flake8-annotations.ignore-fully-untyped = "yes"', 3),
        ("flake8-annotations.ignore-fully-untyped = 1", 3),
        ("flake8-annotations = []", 3),
        ("flake8-annotations.ignore-fully-untyped = false", 0),
        ("flake8-annotations.ignore-fully-untyped = true", 1),
    ],
)
def test_annotation_suppression_shapes_are_validated_before_certification(
    run_project: RunProject, setting: str, exit_code: int
) -> None:
    configuration = PYPROJECT.replace('"T20"]', '"T20", "ANN"]') + setting + '\n[tool.ty.rules]\nall = "error"\n'
    makefile = (
        PYTHON_MAKEFILE.format(format_mode="--check").replace("mypy --strict .", "ty check .").replace("cd app && ", "")
    )
    result, report = run_project({**ANNOTATION_SOURCE, "pyproject.toml": configuration, "Makefile": makefile})
    assert result == exit_code
    assert report["verification_status"] == ("incomplete" if exit_code == 3 else "complete")


@pytest.mark.parametrize(
    "child, exit_code", [("suppress-none-returning = false", 1), ("ignore-fully-untyped = false", 0), ("", 1)]
)
def test_inherited_annotation_suppression_fields_are_preserved_until_explicitly_overridden(
    run_project: RunProject, child: str, exit_code: int
) -> None:
    base = '[lint]\nextend-select = ["S", "ASYNC", "DTZ", "G", "T20", "ANN"]\n'
    base += "[lint.flake8-annotations]\nignore-fully-untyped = true\n"
    configuration = PYPROJECT + '[tool.ty.rules]\nall = "error"\n'
    makefile = (
        PYTHON_MAKEFILE.format(format_mode="--check").replace("mypy --strict .", "ty check .").replace("cd app && ", "")
    )
    result, report = run_project(
        {
            **ANNOTATION_SOURCE,
            "pyproject.toml": configuration,
            "Makefile": makefile,
            "base.toml": base,
            "ruff.toml": 'extend = "base.toml"\n[lint.flake8-annotations]\n' + child,
        }
    )
    assert result == exit_code
    assert report["verification_status"] == "complete"
