from tests.conftest import RunPristine, rule_findings

SOURCE = (
    "#!/usr/bin/env python3\n"
    "import os  # noqa: F401\n"
    "\n"
    "def total(lines):\n"
    '    """Sum the lines."""\n'
    "    # add them up\n"
    "    return sum(lines)  # type: ignore[arg-type]\n"
)


def test_comments_and_docstrings_are_errors_and_directives_are_allowed(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"total.py": SOURCE})
    assert rule_findings(report, "CR-3") == [(5, "error"), (6, "error")]


def test_doc_comments_are_errors(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"total.rs": "/// Sums the lines.\nfn total() {}\n"})
    assert rule_findings(report, "CR-3") == [(1, "error")]


def test_directives_count_only_at_the_start_of_a_comment(run_pristine: RunPristine) -> None:
    source = "def total(lines):\n    return sum(lines)  # the content type: always a list\n"
    _, report = run_pristine({"total.py": source})
    assert rule_findings(report, "CR-3") == [(2, "error")]


def test_python_string_shape_is_no_docstring_elsewhere(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"total.rs": 'fn total() -> &str {\n    "lines"\n}\n'})
    assert rule_findings(report, "CR-3") == []


def test_docstrings_a_framework_decorator_publishes_are_allowed(run_pristine: RunPristine) -> None:
    source = (
        "@mcp.tool(annotations=READ_ONLY)\n"
        "def find_overdue_invoices(customer_identifier):\n"
        '    """List a customer\'s unpaid invoices past their due date."""\n'
        "    return list_overdue_invoices(customer_identifier)\n"
        "\n"
        '@router.get("/invoices", description="Every invoice.")\n'
        "def list_invoices():\n"
        '    """Every invoice."""\n'
        "    return []\n"
        "\n"
        "@cache\n"
        "def invoice_total(invoice):\n"
        '    """Sum the lines."""\n'
        "    return sum(invoice.lines)\n"
    )
    _, report = run_pristine({"invoices.py": source})
    assert rule_findings(report, "CR-3") == [(8, "error"), (13, "error")]
