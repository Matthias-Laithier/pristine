# BS-1 Validate Untrusted Input at the Boundary

Validate untrusted input when it enters the application. Check its type, shape, range, size, and required fields before it reaches domain logic or causes a side effect. Convert valid input into a trusted domain value once. Code behind that boundary may rely on the resulting invariants without repeating defensive checks everywhere.

User input, network responses, files, environment values, command-line arguments, and stored data from outside the present trust boundary are untrusted. Reject invalid input explicitly. Never silently transform invalid data into a different meaning. Normalization is allowed only when it keeps the intended semantics of the value.

## Bad

```python
def create_invoice(invoice_repository, payload):
    invoice = Invoice(
        recipient=payload["recipient"],
        amount_in_cents=payload["amount_in_cents"],
    )
    invoice_repository.save(invoice)
```

Unvalidated data reaches the domain object and the persistence layer. Missing fields, empty recipients, and invalid amounts fail late or become stored state.

## Good

```python
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class CreateInvoiceRequest:
    recipient: str
    amount_in_cents: int


def parse_create_invoice_request(payload):
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")

    recipient = payload.get("recipient")
    amount_in_cents = payload.get("amount_in_cents")

    if not isinstance(recipient, str) or not recipient.strip():
        raise ValueError("recipient must be a non-empty string")
    if type(amount_in_cents) is not int or amount_in_cents <= 0:
        raise ValueError("amount_in_cents must be a positive integer")

    return CreateInvoiceRequest(recipient, amount_in_cents)


def create_invoice(invoice_repository, request):
    invoice_repository.save(Invoice(request.recipient, request.amount_in_cents))
```

The parser owns validation. Domain logic receives one trusted value with explicit invariants and performs no side effect until validation succeeds. [BS-9](bs-9-represent-domain-invariants-in-types.md) owns the trusted representation after the boundary.
