# BS-5 State Changes Are Atomic

An operation that establishes one business invariant either completes fully or leaves state unchanged. When all writes share a transactional boundary, perform them in one transaction. A failure between writes never leaves a partially applied operation.

Independent systems share no local transaction. Commit the application's state and a durable intent in the same transaction, then perform the external effect with an idempotency key and record its completion. When a durable intent is impossible, define a compensating operation and a recovery path. Never hold a local transaction open while waiting on an external system.

An explicitly modeled state such as `pending`, `processing`, or `compensation_required` is valid. An unrecorded half-completed operation is invalid. Every interrupted workflow is observable, retryable, or reversible.

## Bad

```python
def transfer_funds(unit_of_work, transfer):
    with unit_of_work.transaction(
        isolation="serializable",
        timeout=3,
    ) as source_accounts:
        source = source_accounts.get(transfer.source_account_identifier)
        source.debit(transfer.amount_in_cents)
        source_accounts.save(source)

    with unit_of_work.transaction(
        isolation="serializable",
        timeout=3,
    ) as destination_accounts:
        destination = destination_accounts.get(transfer.destination_account_identifier)
        destination.credit(transfer.amount_in_cents)
        destination_accounts.save(destination)
```

Each balance change is race-safe within its own serializable transaction. If the second transaction fails, the source stays debited while the destination receives nothing. The transfer invariant is broken.

## Good

```python
def transfer_funds(unit_of_work, transfer):
    with unit_of_work.transaction(
        isolation="serializable",
        timeout=3,
    ) as account_repository:
        source = account_repository.get(transfer.source_account_identifier)
        destination = account_repository.get(transfer.destination_account_identifier)

        source.debit(transfer.amount_in_cents)
        destination.credit(transfer.amount_in_cents)
        account_repository.save(source)
        account_repository.save(destination)
```

Both balances commit together, and serializable isolation prevents overlapping transfers from losing updates. Any failure rolls the transaction back, so observers see either the complete transfer or no transfer.

See [BS-3](bs-3-bound-every-external-call.md) for retry and timeout requirements, [BS-4](bs-4-do-not-swallow-failures.md) for keeping the failures that trigger rollback or recovery, and [BS-8](bs-8-make-concurrent-state-transitions-race-safe.md) for interference between overlapping operations.
