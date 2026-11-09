import pytest

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


@pytest.mark.parametrize("suffix", ["ts", "tsx"])
def test_double_assertions_through_unknown_are_warnings(run_pristine: RunPristine, suffix: str) -> None:
    source = """const first = invoice as unknown as Record<string, number>;
const second = ((invoice as unknown)) as Invoice;
const third = (invoice as unknown) satisfies unknown;
const fourth = invoice as unknown;
const fifth = invoice as Invoice;
const sixth = invoice as const;
const seventh = invoice as unknown as unknown;
const eighth = payload as {value: unknown};
const ninth: unknown = invoice;
if (typeof ninth === "number") { const total = ninth; }
const tenth = invoice as unknown as (unknown);
const eleventh = invoice as unknown as (unknown | Invoice);
const twelfth = invoice as unknown as (unknown & unknown);
"""
    _, report = run_pristine({f"billing.{suffix}": source})
    assert rule_findings(report, RULE_ID) == [(1, "warning"), (2, "warning")]


def test_angle_bracket_double_assertions_through_unknown_are_warnings(run_pristine: RunPristine) -> None:
    source = """const first = <Invoice><unknown>invoice;
const second = <Invoice>(invoice as unknown);
const third = (<unknown>invoice) as Invoice;
const fourth = <unknown>invoice;
const fifth = <Invoice>invoice;
"""
    _, report = run_pristine({"billing.ts": source})
    assert rule_findings(report, RULE_ID) == [(1, "warning"), (2, "warning"), (3, "warning")]


def test_deeply_parenthesized_unknown_types_do_not_fail_inspection(run_pristine: RunPristine) -> None:
    source = "const total = value as unknown as " + "(\n" * 1100 + "unknown" + "\n)" * 1100 + ";\n"
    _, report = run_pristine({"billing.ts": source})
    assert rule_findings(report, RULE_ID) == []
    assert report["unchecked"] == []
    assert report["verification_status"] == "complete"
    assert report["summary"]["checked_files"] == 1
