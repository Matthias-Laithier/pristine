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
    assert rule_findings(report, "STR-4") == [(5, "error"), (6, "error")]


def test_doc_comments_are_errors(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"total.ts": "/** Sums the lines. */\nfunction total() {}\n"})
    assert rule_findings(report, "STR-4") == [(1, "error")]


def test_directives_count_only_at_the_start_of_a_comment(run_pristine: RunPristine) -> None:
    source = "def total(lines):\n    return sum(lines)  # the content type: always a list\n"
    _, report = run_pristine({"total.py": source})
    assert rule_findings(report, "STR-4") == [(2, "error")]


def test_removed_language_directives_are_comments_in_supported_sources(run_pristine: RunPristine) -> None:
    source = "// go:build linux\n// nolint\n// swiftlint:disable all\n// rustfmt:skip\nconst value = 1;\n"
    _, report = run_pristine({"source.ts": source})
    assert rule_findings(report, "STR-4") == [(1, "error"), (2, "error"), (3, "error"), (4, "error")]


def test_python_string_shape_is_no_docstring_elsewhere(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"total.ts": 'function total(): string {\n    "lines";\n    return "lines";\n}\n'})
    assert rule_findings(report, "STR-4") == []


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
    assert rule_findings(report, "STR-4") == [(8, "error"), (13, "error")]


def test_only_the_first_string_in_a_scope_is_a_docstring(run_pristine: RunPristine) -> None:
    source = 'def total():\n    """Sum the lines."""\n    value = "later"\n    "A later standalone string."\n'
    _, report = run_pristine({"total.py": source})
    assert rule_findings(report, "STR-4") == [(2, "error")]


def test_module_docstring_the_module_reads_is_allowed(run_pristine: RunPristine) -> None:
    read = (
        '"""Generate the OpenAPI schema."""\nimport argparse\n\nparser = argparse.ArgumentParser(description=__doc__)\n'
    )
    unread = '"""Generate the OpenAPI schema."""\nimport argparse\n\nparser = argparse.ArgumentParser(description=main.__doc__)\n'
    named = '"""Build the payload model."""\nmodel = create_model("Payload", __doc__="Payload.")\n'
    _, report = run_pristine({"read.py": read, "unread.py": unread, "named.py": named})
    assert [(finding["path"], finding["line"]) for finding in report["findings"] if finding["check_id"] == "STR-4"] == [
        ("named.py", 1),
        ("unread.py", 1),
    ]


def test_jsdoc_of_only_type_tags_is_allowed_in_javascript(run_pristine: RunPristine) -> None:
    source = (
        "/** @type {import('next').NextConfig} */\n"
        "const config = {};\n"
        "/**\n * @param {string} name\n * @returns {string}\n */\n"
        "const greet = (name) => name;\n"
        "/** @param {string} name the user name */\n"
        "const shout = (name) => name;\n"
    )
    _, report = run_pristine({"config.mjs": source, "config.ts": source})
    assert [(finding["path"], finding["line"]) for finding in report["findings"] if finding["check_id"] == "STR-4"] == [
        ("config.mjs", 8),
        ("config.ts", 1),
        ("config.ts", 3),
        ("config.ts", 8),
    ]
