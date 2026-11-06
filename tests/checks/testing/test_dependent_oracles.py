from tests.conftest import RunPristine, rule_findings

RULE_ID = "TST-7"
REPORTED = """import pytest


class TestInvoice:
    def test_invoice_total_matches(self):
        self.assertEqual(4200, 4200)


def test_order_total_sums_line_totals(order):
    assert order is order
    assert True is True
    assert ("EUR", [1, -2.5]) == ("EUR", [1,  -2.5])
    assert {"currency": "EUR"} == {"currency": "EUR"}
    self.assertIs(None, None)
"""
EXEMPT = """import pytest


def make_order():
    return Order(lines=[])


def test_order_total_is_reported(order, queue, other):
    assert order.total == order.total
    assert order == order
    assert order.lines is order.lines
    assert order.lines[0] is order.lines[0]
    assert [] is []
    assert f"{order}" == f"{order}"
    assert order.total != order.total
    assert order.total is not order.total
    assert order.total == other.total
    assert order.total == order.total == order.total
    assert calculate_order_total_in_cents(order) == calculate_order_total_in_cents(order)
    assert load_store() is load_store()
    with pytest.raises(TypeError):
        assert True is True
    expected = calculate_order_total_in_cents(order)
    assert calculate_order_total_in_cents(order) == expected
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
"""

RAISING = """import unittest
from pytest import raises as fails


class InvoiceCase(unittest.TestCase):
    pass


class TestInvoice(InvoiceCase):
    def test_rejects_negative_totals(self):
        with self.assertRaises(ValueError):
            assert True is True
        with self.assertRaisesRegex(ValueError, "negative"):
            assert None is None


class TestOrder:
    def test_rejects_empty_orders(self):
        with self.assertRaises(ValueError):
            assert True is True


def test_rejects_unknown_currency(validator):
    with fails(ValueError):
        assert False is False
    with validator.raises(ValueError):
        assert False is False
"""


def test_assertions_that_cannot_fail_are_errors(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"tests/test_orders.py": REPORTED})
    expected_lines = [6, 10, 11, 12, 13, 14]
    assert rule_findings(report, RULE_ID) == [(line, "error") for line in expected_lines]


def test_assertions_that_can_fail_are_exempt(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"tests/test_orders.py": EXEMPT})
    assert rule_findings(report, RULE_ID) == []


def test_production_code_is_exempt(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"orders/pricing.py": REPORTED})
    assert rule_findings(report, RULE_ID) == []


def test_only_resolved_raising_contexts_exempt_assertions(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"tests/test_invoice.py": RAISING})
    assert rule_findings(report, RULE_ID) == [(20, "error"), (27, "error")]
