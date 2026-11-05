# BS-12 Handlers of Redelivered Work Are Idempotent

Every handler that can receive the same logical event more than once is idempotent: queue and stream consumers, webhook receivers, scheduled jobs, workflow activities, and HTTP operations that clients retry. Processing a delivery twice leaves the same state and performs each external effect once. Derive a key from the stable identity of the event. Record it with the state change in one transaction, and pass it as the idempotency key of every external effect that supports one.

At-least-once delivery is the contract of every queue, webhook provider, and workflow engine. A retry after a timeout also fires when the first attempt succeeded and only its response was lost. A duplicate charge or a duplicate email cannot be rolled back.

The exceptions:
- Effects that are idempotent by nature, such as setting a value, an upsert by natural key, or a delete by identifier.
- Providers without an idempotency mechanism. Record the intent before the effect, check it on redelivery, and document the remaining duplicate window.

[BS-3](bs-3-bound-every-external-call.md) owns the decision of a caller to retry. This rule owns surviving redelivery. [BS-5](bs-5-state-changes-are-atomic.md) owns the durable intent, and [BS-6](bs-6-make-concurrent-state-transitions-race-safe.md) owns two deliveries processed at the same time.

## Bad

```python
def handle_order_placed(payment_gateway, event):
    payment_gateway.charge(
        event.customer_identifier,
        event.amount_in_cents,
        timeout=3,
    )
```

The broker redelivers the event after a lost acknowledgement, and the customer pays twice.

## Good

```python
def handle_order_placed(payment_gateway, event):
    payment_gateway.charge(
        event.customer_identifier,
        event.amount_in_cents,
        idempotency_key=f"order-placed-{event.order_identifier}",
        timeout=3,
    )
```

A redelivery carries the same key, and the gateway returns the first charge without creating a second one.
