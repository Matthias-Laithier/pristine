import pytest

from tests.conftest import RunPristine, rule_findings


@pytest.mark.parametrize(
    ("line_count", "expected", "expected_exit"),
    [(150, [], 0), (151, [], 0), (200, [], 0), (201, [(1, "error")], 1)],
)
def test_file_size_limits(
    run_pristine: RunPristine, line_count: int, expected: list[tuple[int, str]], expected_exit: int
) -> None:
    source = "".join(f"value_{index} = {index}\n" for index in range(line_count))
    exit_code, report = run_pristine({"values.py": source})
    assert rule_findings(report, "STR-1") == expected
    assert exit_code == expected_exit
    assert report["summary"]["warnings"] == 0
    assert report["summary"]["checked_files"] == 1
    assert report["verification_status"] == "complete"
    if expected:
        assert report["findings"][0]["message"] == (
            "file has 201 lines (hard limit 200); split it along clean boundaries"
        )


@pytest.mark.parametrize("ending", ["", "\n"])
@pytest.mark.parametrize(("line_count", "expected"), [(200, []), (201, [(1, "error")])])
def test_file_size_counts_blank_lines_and_the_unterminated_last_line(
    run_pristine: RunPristine, ending: str, line_count: int, expected: list[tuple[int, str]]
) -> None:
    source = "\n" * (line_count - 1) + "value = 1" + ending
    _, report = run_pristine({"values.py": source})
    assert rule_findings(report, "STR-1") == expected
    assert report["summary"]["checked_files"] == 1
    assert report["verification_status"] == "complete"
