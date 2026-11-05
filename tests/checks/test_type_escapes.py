from tests.conftest import RunPristine, rule_findings

RULE_ID = "CR-21"
PYTHON_SOURCE = """import typing as t
from typing import Any, TypeVar, cast
InvoiceT = TypeVar("InvoiceT")
def total(invoice: Any, *lines: t.Any) -> dict[str, Any]:
    return cast(dict[str, int], invoice)
def first(invoices: list[InvoiceT]) -> InvoiceT:
    return invoices[0]  # type: ignore
import billing_sdk  # type: ignore[import-untyped]
summary = invoice.summary  # pyright: ignore
payload = {"Any": "typing.Any"}
"""
SCRIPT_SOURCE = """// @ts-nocheck
export function total(invoice: any, lines: Array<any>): number {
  // @ts-ignore
  const amount = (invoice as any).amount as number;
  // @ts-expect-error legacy field
  return lines.length + amount + invoice.tax!;
}
export function first<InvoiceT>(invoices: InvoiceT[]): unknown {
  return invoices[0];
}
"""


def test_python_any_and_bare_suppressions_are_errors_and_cast_is_a_warning(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"billing.py": PYTHON_SOURCE})
    expected = [(4, "error"), (4, "error"), (4, "error"), (5, "warning"), (7, "error"), (9, "error")]
    assert sorted(rule_findings(report, RULE_ID)) == expected


def test_script_any_and_suppressions_are_errors_and_non_null_is_a_warning(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"billing.ts": SCRIPT_SOURCE})
    expected = [(1, "error"), (2, "error"), (2, "error"), (3, "error"), (4, "error"), (6, "warning")]
    assert sorted(rule_findings(report, RULE_ID)) == expected


def test_declaration_files_are_skipped(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"billing.d.ts": SCRIPT_SOURCE})
    assert rule_findings(report, RULE_ID) == []
