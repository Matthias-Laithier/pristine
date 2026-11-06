import pytest

from tests.project.conftest import RunProject
from tests.project.linting.lint_cases import lint_messages, with_python_lint_config


def test_ruff_requires_all_required_rule_sets(run_project: RunProject) -> None:
    assert lint_messages(with_python_lint_config('[tool.ruff.lint]\nselect = ["S"]\n'), run_project) == [
        (
            "Ruff does not enable the required rule sets (ASYNC, DTZ, G, T20); select or extend-select "
            'the S, ASYNC, DTZ, G, and T20 rule sets (or "ALL")'
        )
    ]


def test_ruff_accepts_all_targeted_ignores_and_inheritance(run_project: RunProject) -> None:
    files = {
        **with_python_lint_config(
            '[tool.ruff]\nextend = "./ruff-base.toml"\n[tool.ruff.lint]\nextend-select = ["S"]\n'
        ),
        "ruff-base.toml": 'extend = "./ruff-defaults.toml"\n[lint]\nextend-select = ["ASYNC", "DTZ", "G", "T20"]\n[lint.per-file-ignores]\n"tests/**" = ["S101"]\n',
        "ruff-defaults.toml": '[lint]\nextend-select = ["S"]\n',
    }
    assert lint_messages(files, run_project) == []


def test_ruff_accumulates_inherited_extended_per_file_ignores(run_project: RunProject) -> None:
    files = {
        **with_python_lint_config(
            '[tool.ruff]\nextend = "config/ruff.toml"\n'
            '[tool.ruff.lint]\nselect = ["ALL"]\n'
            '[tool.ruff.lint.extend-per-file-ignores]\n"*" = ["D100"]\n'
        ),
        "config/ruff.toml": '[lint]\nselect = ["ALL"]\n[lint.extend-per-file-ignores]\n"*" = ["S"]\n',
    }
    shortfall = (
        "Ruff does not enable the required rule sets (S); select or extend-select the S, ASYNC, DTZ, G, "
        'and T20 rule sets (or "ALL")'
    )
    assert [message for message in lint_messages(files, run_project) if message == shortfall] == [shortfall]


def test_ruff_global_ignore_disables_all_selection(run_project: RunProject) -> None:
    files = with_python_lint_config('[tool.ruff.lint]\nextend-select = ["ALL"]\nignore = ["S"]\n')
    assert lint_messages(files, run_project) == [
        (
            "Ruff does not enable the required rule sets (S); select or extend-select the S, ASYNC, DTZ, G, "
            'and T20 rule sets (or "ALL")'
        )
    ]


def test_ruff_dynamic_config_is_explicitly_unverifiable(run_project: RunProject) -> None:
    files = with_python_lint_config('[tool.ruff]\nextend = "ruff-${mode}.toml"\n')
    _, report = run_project(files)
    finding = next(finding for finding in report["findings"] if finding["rule_id"] == "TL-3")
    assert finding["kind"] == "verification"
    assert finding["message"] == (
        "cannot verify that the Ruff rule sets are configured: pyproject.toml refers to ruff-${mode}.toml, "
        "which is not a file of the repository"
    )


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        (
            with_python_lint_config('[tool.ruff]\nextend = "../outside.toml"\n'),
            [
                (
                    "cannot verify that the Ruff rule sets are configured: pyproject.toml refers to ../outside.toml, "
                    "which is not a file of the repository"
                )
            ],
        ),
        (
            with_python_lint_config(
                '[tool.ruff]\nextend = "./ruff-base.toml"\n',
                {"ruff-base.toml": '[lint]\nselect = ["ALL"]\nignore = ["S"]\n'},
            ),
            [
                (
                    "Ruff does not enable the required rule sets (S); select or extend-select the S, ASYNC, DTZ, G, "
                    'and T20 rule sets (or "ALL")'
                )
            ],
        ),
        (
            with_python_lint_config(
                '[tool.ruff]\nextend = "./ruff-base.toml"\n[tool.ruff.lint]\nselect = ["ALL"]\n',
                {"ruff-base.toml": '[lint]\nselect = ["ALL"]\nignore = ["S"]\n'},
            ),
            [],
        ),
        (
            with_python_lint_config(
                '[tool.ruff]\nextend = "./ruff-base.toml"\n[tool.ruff.lint]\nselect = ["S"]\n',
                {"ruff-base.toml": '[lint]\nselect = ["S"]\nextend-select = ["ASYNC", "DTZ", "G", "T20"]\n'},
            ),
            [
                (
                    "Ruff does not enable the required rule sets (ASYNC, DTZ, G, T20); select or extend-select "
                    'the S, ASYNC, DTZ, G, and T20 rule sets (or "ALL")'
                )
            ],
        ),
        (
            with_python_lint_config(
                '[tool.ruff]\nextend = "./ruff-base.toml"\n[tool.ruff.lint]\nselect = ["ALL"]\n',
                {"ruff-base.toml": '[lint]\nselect = ["ALL"]\nextend-ignore = ["S"]\n'},
            ),
            [],
        ),
        (
            with_python_lint_config('[tool.ruff.lint]\nselect = ["ALL"]\nignore = ["ALL"]\n'),
            [
                (
                    "Ruff does not enable the required rule sets (S, ASYNC, DTZ, G, T20); select or extend-select "
                    'the S, ASYNC, DTZ, G, and T20 rule sets (or "ALL")'
                )
            ],
        ),
        (
            with_python_lint_config('[tool.ruff.lint]\nselect = ["S", "ASYNC", "DTZ", "G", "T20"]\nignore = ["ALL"]\n'),
            [],
        ),
        (
            with_python_lint_config('[tool.ruff.lint]\nextend-select = ["ALL"]\nextend-ignore = ["S"]\n'),
            [
                (
                    "Ruff does not enable the required rule sets (S); select or extend-select the S, ASYNC, DTZ, G, "
                    'and T20 rule sets (or "ALL")'
                )
            ],
        ),
        (
            with_python_lint_config(
                '[tool.ruff.lint]\nselect = ["S", "ASYNC", "DTZ", "G", "T20"]\nper-file-ignores = {"*" = ["S"]}\n'
            ),
            [
                (
                    "Ruff does not enable the required rule sets (S); select or extend-select the S, ASYNC, DTZ, G, "
                    'and T20 rule sets (or "ALL")'
                )
            ],
        ),
    ],
)
def test_ruff_rule_proofs(run_project: RunProject, files: dict[str, str], expected: list[str]) -> None:
    assert lint_messages(files, run_project) == expected
