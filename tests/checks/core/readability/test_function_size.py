import pytest

from tests.conftest import RunPristine, rule_findings


def python_function(statement_count: int) -> str:
    body = "".join(f"    total_{index} = {index}\n\n" for index in range(statement_count - 1))
    return f"def compute():\n{body}"


def python_match(final_pattern: str, clause: str = "return 0", prefix: str = "") -> str:
    cases = "".join(f"        case {index}:\n            return {index}\n" for index in range(24))
    return f"def label(value):\n{prefix}    match value:\n{cases}        case {final_pattern}:\n            {clause}\n"


@pytest.mark.parametrize(
    ("line_count", "expected"),
    [(30, []), (31, [(1, "warning")]), (50, [(1, "warning")]), (51, [(1, "error")])],
)
def test_function_size_limits_ignore_blank_lines(
    run_pristine: RunPristine, line_count: int, expected: list[tuple[int, str]]
) -> None:
    _, report = run_pristine({"compute.py": python_function(line_count)})
    assert rule_findings(report, "STR-2") == expected


def test_typescript_methods_are_measured(run_pristine: RunPristine) -> None:
    body = "".join(f"    const total{index} = {index};\n" for index in range(50))
    _, report = run_pristine({"invoice.ts": f"class Invoice {{\n  total() {{\n{body}  }}\n}}\n"})
    assert rule_findings(report, "STR-2") == [(2, "error")]


@pytest.mark.parametrize(
    ("pattern", "clause", "prefix", "expected"),
    [
        ("_", "return 0", "", []),
        ("remaining", "return 0", "", []),
        ("24", "return 0", "", [(1, "error")]),
        ("None", "return 0", "", [(1, "error")]),
        ("True", "return 0", "", [(1, "error")]),
        ("Status.paid", "return 0", "", [(1, "error")]),
        ("_ if value", "return 0", "", [(1, "error")]),
        ("_", "value = 0\n            return value", "", [(1, "error")]),
        ("_", "return 0", "    prepare(value)\n", [(1, "error")]),
        ("_", "while value:\n                value -= 1", "", [(1, "error")]),
        ("_", "return (\n                value\n            )", "", [(1, "error")]),
    ],
)
def test_only_exhaustive_single_clause_match_is_exempt(
    run_pristine: RunPristine, pattern: str, clause: str, prefix: str, expected: list[tuple[int, str]]
) -> None:
    _, report = run_pristine({"label.py": python_match(pattern, clause, prefix)})
    assert rule_findings(report, "STR-2") == expected
