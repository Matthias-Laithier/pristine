import pytest

from tests.conftest import RunPristine, rule_findings


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("f\"SELECT number FROM invoices WHERE recipient_email = '{recipient_email}'\"", [(2, "error")]),
        (
            '"SELECT number FROM invoices WHERE recipient_email = :recipient_email", {"recipient_email": recipient_email}',
            [],
        ),
    ],
)
def test_fetch_all_queries_require_bound_values(
    run_pristine: RunPristine, query: str, expected: list[tuple[int, str]]
) -> None:
    source = (
        "def find_invoices(database, recipient_email):\n"
        "    return database.fetch_all(\n"
        f"        {query}, timeout=3,\n"
        "    )\n"
    )
    _, report = run_pristine({"invoices.py": source})
    assert rule_findings(report, "SAFE-6") == expected
