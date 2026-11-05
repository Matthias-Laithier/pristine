# CR-17 Keep Function Signatures Cohesive

A function signature exposes one cohesive operation. Group values that form one validated domain concept into a domain value. Split operations when boolean flags, mode strings, or optional parameters select substantially different behavior. Never make callers coordinate a loose collection of primitives that only becomes meaningful inside the function.

Impose no arbitrary limit on the parameter count. Several independent collaborators can be clearer than a container created only to shorten a signature. Create a parameter object when its fields share invariants, travel together across boundaries, or have a domain name. Never hide unrelated dependencies in a generic context object.

A boolean is fine when it represents data. It is wrong when it secretly chooses which operation the function performs. [CO-4](co-4-clear-interfaces.md) owns the full contract. This rule owns the shape of its inputs.

## Bad

```python
def create_invoice(
    invoice_repository,
    recipient_email,
    currency_code,
    amount_in_cents,
    send_immediately,
    save_as_draft,
): ...
```

The caller can request contradictory modes, and three primitives that form one invoice request have no shared validation boundary.

## Good

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CreateInvoiceRequest:
    recipient_email: str
    currency_code: str
    amount_in_cents: int

    def __post_init__(self):
        if "@" not in self.recipient_email:
            raise ValueError("recipient_email must be valid")
        if self.currency_code not in SUPPORTED_CURRENCY_CODES:
            raise ValueError("currency_code is not supported")
        if type(self.amount_in_cents) is not int or self.amount_in_cents <= 0:
            raise ValueError("amount_in_cents must be positive")


def create_draft_invoice(invoice_repository, request): ...


def create_and_send_invoice(invoice_repository, mailer, request): ...
```

The request names one domain concept. Drafting and sending are distinct operations, so callers cannot construct a contradictory flag combination.
