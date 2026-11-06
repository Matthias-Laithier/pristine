import pytest

from tests.conftest import RunPristine, rule_findings


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_complete_script_metadata_is_allowed_and_surrounding_comments_are_errors(
    run_pristine: RunPristine, newline: str
) -> None:
    source = newline.join(
        (
            "# explain the script",
            "# /// script",
            '# requires-python = ">=3.11"',
            '# dependencies = ["playwright>=1.47"]',
            "# ///",
            "import playwright",
            "# explain the import",
        )
    )
    _, report = run_pristine({"release.py": source})
    assert rule_findings(report, "CR-3") == [(1, "error"), (7, "error")]


@pytest.mark.parametrize(
    ("source", "expected_lines"),
    [
        ('# /// script\n# dependencies = ["playwright>=1.47"]\nimport playwright\n', [1, 2]),
        ('# /// tool\n# dependencies = ["playwright>=1.47"]\n# ///\nimport playwright\n', [1, 2, 3]),
        ("# /// script metadata\n# ///\nimport playwright\n", [1, 2]),
    ],
)
def test_incomplete_or_non_script_metadata_stays_an_error(
    run_pristine: RunPristine, source: str, expected_lines: list[int]
) -> None:
    _, report = run_pristine({"invalid.py": source})
    assert rule_findings(report, "CR-3") == [(line, "error") for line in expected_lines]


def test_script_metadata_blocks_after_code_are_allowed(run_pristine: RunPristine) -> None:
    source = (
        "# /// script\n"
        '# dependencies = ["playwright>=1.47"]\n'
        "# ///\n"
        "import playwright\n"
        "# /// script\n"
        '# dependencies = ["pytest>=8"]\n'
        "# ///\n"
        "import pytest\n"
    )
    _, report = run_pristine({"release.py": source})
    assert rule_findings(report, "CR-3") == []
