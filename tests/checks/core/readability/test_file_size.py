import pytest

from tests.conftest import RunPristine, rule_findings


@pytest.mark.parametrize(
    ("line_count", "expected"),
    [(150, []), (151, [(1, "warning")]), (200, [(1, "warning")]), (201, [(1, "error")])],
)
def test_file_size_limits(run_pristine: RunPristine, line_count: int, expected: list[tuple[int, str]]) -> None:
    source = "".join(f"value_{index} = {index}\n" for index in range(line_count))
    _, report = run_pristine({"values.py": source})
    assert rule_findings(report, "CR-1") == expected
