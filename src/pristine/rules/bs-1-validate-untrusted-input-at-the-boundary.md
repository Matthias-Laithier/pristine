# BS-1 Validate Untrusted Input at the Boundary

Validate untrusted input when it enters the application, model output and configuration included. Check its type, shape, range, size, and required fields before it reaches domain logic or causes a side effect. Convert valid input into a trusted domain value once. Code behind that boundary may rely on the resulting invariants without repeating defensive checks everywhere. Parse model output into a schema, and parse every setting once, at startup, into one typed settings value.

User input, network responses, files, environment values, command-line arguments, model output, and stored data from outside the present trust boundary are untrusted. Reject invalid input explicitly. Never silently transform invalid data into a different meaning. Normalization is allowed only when it keeps the intended semantics of the value.

## Model output
Model output, tool-call arguments chosen by a model, and retrieved documents are untrusted input, whatever prompt produced them. Parse model output into a schema, using the provider's structured output where it exists. Output that fails the schema is a failure, retried a bounded number of times within the deadline of [BS-3](bs-3-bound-every-external-call.md). Never extract fields with regular expressions and fall back to a default. [BS-10](bs-10-untrusted-values-never-change-the-structure-of-a-query-command-markup-or-path.md) owns model output that reaches an interpreter.

## Settings
Configuration is input too. Every setting is parsed once, at startup, into a typed settings value, and a missing or invalid required setting fails startup. In Python, use a `pydantic-settings` `BaseSettings` model. In other ecosystems, use their established typed settings library where one exists. Otherwise, read the environment once at startup in a single settings module and validate every value there.

Reading the environment at that startup boundary is fine. Scattered environment reads in the code are forbidden, and so are defaults that silently stand in for required values. The composition root builds the settings value and passes it on. Importing a module never builds it ([CO-13](co-13-imports-do-not-perform-external-work.md)). Secrets among the settings follow [BS-2](bs-2-keep-secrets-out-of-code-and-output.md).

## Bad: request payload

```python
def create_invoice(invoice_repository, payload):
    invoice = Invoice(
        recipient=payload["recipient"],
        amount_in_cents=payload["amount_in_cents"],
    )
    invoice_repository.save(invoice)
```

Unvalidated data reaches the domain object and the persistence layer. Missing fields, empty recipients, and invalid amounts fail late or become stored state.

## Good: request payload

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

The parser owns validation. Domain logic receives one trusted value with explicit invariants and performs no side effect until validation succeeds. [BS-7](bs-7-represent-domain-invariants-in-types.md) owns the trusted representation after the boundary.

## Bad: settings

```python
import os
from datetime import timedelta


def schedule_payment_reminder(reminder_queue, invoice):
    payment_term_days = int(os.environ.get("PAYMENT_TERM_DAYS", "30"))
    reminder_queue.schedule(invoice.number, invoice.issued_on + timedelta(days=payment_term_days))
```

A deployment that forgets the variable silently runs with thirty days, and a typo such as `30d` crashes the first reminder hours after startup. Nobody can list the settings the application needs without reading every function.

## Good: settings

```python
from datetime import timedelta

from pydantic import PositiveInt
from pydantic_settings import BaseSettings


class BillingSettings(BaseSettings):
    payment_term_days: PositiveInt


def schedule_payment_reminder(reminder_queue, invoice, payment_term_days):
    reminder_queue.schedule(invoice.number, invoice.issued_on + timedelta(days=payment_term_days))


def main():
    billing_settings = BillingSettings()
    run_billing(billing_settings)
```

A missing or malformed setting stops the process at startup with the name of the field. The settings class lists every value the application reads, and the code behind it receives a positive integer.
