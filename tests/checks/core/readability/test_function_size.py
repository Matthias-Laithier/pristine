import pytest

from tests.conftest import RunPristine, rule_findings


def python_function(statement_count: int) -> str:
    body = "".join(f"    total_{index} = {index}\n\n" for index in range(statement_count - 1))
    return f"def compute():\n{body}"


@pytest.mark.parametrize(
    ("line_count", "expected"),
    [(30, []), (31, [(1, "warning")]), (50, [(1, "warning")]), (51, [(1, "error")])],
)
def test_function_size_limits_ignore_blank_lines(
    run_pristine: RunPristine, line_count: int, expected: list[tuple[int, str]]
) -> None:
    _, report = run_pristine({"compute.py": python_function(line_count)})
    assert rule_findings(report, "CR-12") == expected


def test_typescript_methods_are_measured(run_pristine: RunPristine) -> None:
    body = "".join(f"    const total{index} = {index};\n" for index in range(50))
    _, report = run_pristine({"invoice.ts": f"class Invoice {{\n  total() {{\n{body}  }}\n}}\n"})
    assert rule_findings(report, "CR-12") == [(2, "error")]
