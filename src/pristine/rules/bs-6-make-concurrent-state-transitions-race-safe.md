# BS-6 Make Concurrent State Transitions Race-Safe

Every read-modify-write transition that can overlap with another execution stays correct under concurrency. Enforce the precondition and the write as one indivisible operation, with a conditional update, a version check, a constraint, a lock, a serializable transaction, a queue partition, or an equivalent mechanism.

Reading, checking, and writing separately is unsafe even when each step is atomic on its own. On conflict, fail, retry from fresh state, or apply an explicitly defined resolution. Never silently overwrite newer state.

A documented, enforced single-writer architecture is the exception. An assumption that concurrent execution is unlikely is no exception.

## Bad

```python
def reserve_stock(product_repository, product_identifier, quantity):
    product = product_repository.get(
        product_identifier,
        timeout=3,
    )
    if product.available_quantity < quantity:
        raise InsufficientStock

    product.available_quantity -= quantity
    product_repository.save(product, timeout=3)
```

Two callers can read the same available quantity, both pass the check, and both reserve stock that does not exist.

## Good

```python
def reserve_stock(product_repository, product_identifier, quantity):
    reserved = product_repository.decrement_if_available(
        product_identifier,
        quantity,
        timeout=3,
    )
    if not reserved:
        raise InsufficientStock
```

The repository performs the availability check and the decrement as one conditional write. Competing callers cannot both consume the same stock.

[BS-5](bs-5-state-changes-are-atomic.md) owns partial completion across related writes. This rule owns interference between overlapping operations.
