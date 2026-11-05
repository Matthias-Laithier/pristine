# BS-4 Do Not Swallow Failures

Handle a failure only when the present boundary can recover, add meaningful context, or translate it into its own contract. Otherwise let it propagate. Never catch an exception and return success, `None`, an empty value, or fabricated data that makes the failure invisible.

When translating an exception, keep its cause. Release resources and roll back partial work through context managers, transactions, or `finally`. A top-level request or process boundary may catch broadly to produce a safe response and record the failure. It never pretends the operation succeeded and never exposes secrets to the caller.

## Bad

```python
from typing import Protocol


class PaymentGateway(Protocol):
    def charge(
        self,
        customer_identifier,
        amount_in_cents,
        timeout,
    ) -> PaymentReceipt: ...


class PaymentService:
    def __init__(self, payment_gateway: PaymentGateway):
        self.payment_gateway = payment_gateway

    def charge_customer(self, customer_identifier, amount_in_cents):
        try:
            return self.payment_gateway.charge(
                customer_identifier,
                amount_in_cents,
                timeout=3,
            )
        except Exception:
            return None
```

The caller cannot distinguish a failed charge from an absent result, and the original failure disappears.

## Good

```python
from typing import Protocol


class PaymentGateway(Protocol):
    def charge(
        self,
        customer_identifier,
        amount_in_cents,
        timeout,
    ) -> PaymentReceipt: ...


class PaymentService:
    def __init__(self, payment_gateway: PaymentGateway):
        self.payment_gateway = payment_gateway

    def charge_customer(self, customer_identifier, amount_in_cents):
        try:
            return self.payment_gateway.charge(
                customer_identifier,
                amount_in_cents,
                timeout=3,
            )
        except PaymentGatewayError as error:
            raise PaymentFailed(customer_identifier) from error
```

The service translates a dependency failure into its domain contract and keeps the original cause for diagnosis. [BS-9](bs-9-boundaries-expose-stable-error-contracts.md) owns the shape of that contract.
