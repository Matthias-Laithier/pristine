# CO-4 Clear Interfaces

A composable unit has a clear interface. The interface is the contract. The consumer never needs to know the internals. A unit with a leaky interface is not composable, because consumers come to depend on details that should stay hidden.

## Bad

```python
class OrderStorageUnavailable(Exception):
    pass


class FileOrderStorage:
    def __init__(self, path):
        self.path = path


def save_orders(file_appender, storage, orders):
    for order in orders:
        try:
            file_appender.append_atomically(
                storage.path,
                serialize_order(order),
            )
        except RecordAppendError as error:
            raise OrderStorageUnavailable from error
```

`save_orders` reaches into the internals of the storage object and depends on its filesystem implementation. Changing the storage mechanism breaks the consumer.

## Good

```python
from typing import Protocol


class OrderStorageUnavailable(Exception):
    pass


class OrderStorage(Protocol):
    def save(self, order) -> None: ...


class FileOrderStorage:
    def __init__(self, record_appender, path):
        self.record_appender = record_appender
        self.path = path

    def save(self, order) -> None:
        try:
            self.record_appender.append_atomically(
                self.path,
                serialize_order(order),
            )
        except RecordAppendError as error:
            raise OrderStorageUnavailable from error


def save_orders(storage: OrderStorage, orders):
    for order in orders:
        storage.save(order)
```

`save_orders` depends only on the `save` contract. A different storage implementation can replace `FileOrderStorage` without changing the consumer.

[CO-11](co-11-export-only-the-public-contract.md) owns how much of an interface is exposed. [CR-17](cr-17-keep-function-signatures-cohesive.md) owns the shape of its inputs. [BS-11](bs-11-boundaries-expose-stable-error-contracts.md) owns its failures.
