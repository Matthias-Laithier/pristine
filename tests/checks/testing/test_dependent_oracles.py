from tests.conftest import RunPristine, rule_findings

RULE_ID = "TST-7"
REPORTED = """import pytest


class TestInvoice:
    def test_invoice_total_matches(self):
        self.assertEqual(invoice.total_in_cents, invoice.total_in_cents)


def test_order_total_sums_line_totals(order):
    assert order.total == order.total
    assert True is True
    assert (order.lines[0]) == ( order.lines[0] )
    expected = calculate_order_total_in_cents(order)
    assert calculate_order_total_in_cents(order) == expected
    total = pricing.order_total(order)
    assert total == pricing.order_total(order)
"""
EXEMPT = """import pytest


def make_order():
    return Order(lines=[])


def test_order_total_is_reported(order, queue, other):
    assert order.total != order.total
    assert order.total is not order.total
    assert order.total == other.total
    assert order.total == order.total == order.total
    assert calculate_order_total_in_cents(order) == calculate_order_total_in_cents(order)
    assert load_store() is load_store()
    with pytest.raises(TypeError):
        assert order.total == order.total
    expected = calculate_order_total_in_cents(order)
    assert calculate_order_total_in_cents(other) == expected
    expected = calculate_order_total_in_cents(order)
    order.add_line(Line(unit_price_in_cents=100, quantity=1))
    assert calculate_order_total_in_cents(order) == expected
    expected = make_order()
    assert make_order() == expected
    expected = Money(4200)
    assert Money(4200) == expected
    expected = next(queue)
    assert next(queue) == expected
    service = runtime.data_qa()
    assert runtime.data_qa() is service
    expected = await pricing.total(order)
    assert await pricing.total(order) == expected
    assert decode(encode(order)) == order
    self.assertEqual(order.total, 4200)


def test_order_total_is_deterministic(order):
    assert order.total == order.total
    expected = calculate_order_total_in_cents(order)
    assert calculate_order_total_in_cents(order) == expected


def test_order_lines_returns_copy(order):
    assert order.lines is not order.lines
    assert order.lines == order.lines
"""


def test_assertions_that_cannot_fail_are_errors(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"tests/test_orders.py": REPORTED})
    expected_lines = [6, 10, 11, 12, 14, 16]
    assert rule_findings(report, RULE_ID) == [(line, "error") for line in expected_lines]


def test_independent_or_property_assertions_are_exempt(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"tests/test_orders.py": EXEMPT})
    assert rule_findings(report, RULE_ID) == []


def test_production_code_is_exempt(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"orders/pricing.py": REPORTED})
    assert rule_findings(report, RULE_ID) == []
