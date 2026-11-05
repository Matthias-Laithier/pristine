# BS-9 Boundaries Expose Stable Error Contracts

A public boundary defines the failures its callers may receive. Translate framework, SDK, database, transport, and operating-system errors into a small set of errors the boundary owns. Callers never need to import the exception types of a dependency or inspect error-message text to decide what happened.

Keep the original cause when translating. Include only context that is safe and useful. Distinguish failures only when callers can respond differently, such as invalid input, conflict, unavailable dependency, or exhausted capacity. Never create one exception class per internal failure.

Let unexpected programming defects propagate to the top-level failure handler. Never relabel every exception as an operational error. [BS-4](bs-4-do-not-swallow-failures.md) owns whether a failure may be handled. This rule owns the contract after a boundary translates it.

## Bad

```python
def charge_customer(payment_client, customer_identifier, amount_in_cents):
    return payment_client.charge(
        customer_identifier,
        amount_in_cents,
        timeout=3,
    )
```

Every caller must understand the exception hierarchy of the payment SDK, and replacing the SDK changes the service contract.

## Good

```python
class PaymentUnavailable(Exception):
    pass


def charge_customer(payment_client, customer_identifier, amount_in_cents):
    try:
        return payment_client.charge(
            customer_identifier,
            amount_in_cents,
            timeout=3,
        )
    except PaymentClientUnavailable as error:
        raise PaymentUnavailable from error
```

Callers depend on a failure the application owns. The original error of the dependency stays available as the cause for diagnosis.
