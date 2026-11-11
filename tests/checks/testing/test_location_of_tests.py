import pytest

from tests.conftest import RunPristine, rule_findings

TEST_BODY = "def test_total():\n    assert True\n"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("backend/src/test_invoice.py", [(1, "error")]),
        ("backend/src/invoice_test.py", [(1, "error")]),
        ("frontend/src/InvoiceList.test.jsx", [(1, "error")]),
        ("frontend/src/invoice.spec.ts", [(1, "error")]),
        ("backend/src/invoice_test.ts", [(1, "error")]),
        ("backend/test_generation/test_invoice.py", [(1, "error")]),
        ("backend/tests/payments/test_invoice.py", []),
        ("frontend/test/InvoiceList.test.jsx", []),
        ("backend/integration_tests/test_invoice.py", []),
        ("service/src/test/java/invoice.spec.ts", []),
        ("backend/src/payments/tests/test_invoice.py", [(1, "warning")]),
        ("backend/scripts/test_connection.py", []),
    ],
)
def test_test_file_location(run_pristine: RunPristine, path: str, expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine({path: TEST_BODY})
    assert rule_findings(report, "TEST-2") == expected


def test_jest_folder_inside_source_is_a_warning(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"frontend/src/components/__tests__/fixtures.ts": "export const total = 1;\n"})
    assert rule_findings(report, "TEST-2") == [(1, "warning")]


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({"backend/conftest.py": TEST_BODY, "backend/pyproject.toml": "[project]\nname = 'billing'\n"}, []),
        ({"backend/tests/conftest.py": TEST_BODY}, []),
        ({"backend/src/conftest.py": TEST_BODY}, [(1, "warning")]),
    ],
)
def test_conftest_location(run_pristine: RunPristine, files: dict[str, str], expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine(files)
    assert rule_findings(report, "TEST-2") == expected
