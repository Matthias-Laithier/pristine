# CR-21 Never Escape the Type Checker

Code passes the project's type checker without escape hatches. Never silence a type error with `Any`, `any`, `cast`, a non-null assertion, a bare `# type: ignore`, `@ts-ignore`, `@ts-nocheck`, or a definition left unannotated. A value whose type is unknown is untrusted. Annotate it as `object` or `unknown` and narrow it by parsing (see [BS-1](bs-1-validate-untrusted-input-at-the-boundary.md)). A third-party library without types is wrapped once in its service with a typed interface (see [CO-6](co-6-wrap-external-clients-in-singleton-services.md)), so the untyped surface stays in one file.

An escape hatch turns the checker off exactly where the code is least certain. A renamed field, a missing case, or a wrong return type then fails in production, where `make check` would have caught it for free.

The exceptions:
- A defect or a missing stub in a dependency. Suppress the single line with its error code, such as `# type: ignore[import-untyped]`, inside the service that wraps the dependency.
- Plumbing the type system cannot express, such as a generic decorator. Use the narrowest construct first: `TypeVar`, `ParamSpec`, overloads, or a recursive JSON alias.

[CR-3](cr-3-no-comments-except-machine-read-text.md) allows a suppression directive as machine-read text. This rule owns when one is acceptable. [TL-3](tl-3-automate-formatting-and-static-analysis.md) owns configuring and running the checker.

## Bad

```python
from typing import Any


def invoice_numbers(billing_client: Any, account_identifier: str) -> list[str]:
    page = billing_client.list_invoices(account_identifier, timeout=3)
    return [invoice.number for invoice in page.items]
```

The checker accepts any attribute on the client. A typo such as `page.itmes` or a renamed SDK field passes `make check` and fails at runtime.

## Good

```python
from typing import Protocol


class BillingClient(Protocol):
    def list_invoices(self, account_identifier: str, timeout: float) -> InvoicePage: ...


def invoice_numbers(billing_client: BillingClient, account_identifier: str) -> list[str]:
    page = billing_client.list_invoices(account_identifier, timeout=3)
    return [invoice.number for invoice in page.items]
```

The contract is typed, so the checker verifies every attribute the function reads.
