# CO-3 Design for Combination Over Modification

When adding a behavior variant, combine units. Never modify or subclass a stable unit only to create that variant. Units are open for extension and closed for modification. Bug fixes and intentional changes to the existing contract belong in the unit that owns that behavior. This rule owns behavior extension. [CO-1](co-1-favor-composition-over-inheritance.md) owns the relationship between objects.

Both examples implement the same explicit contract:

```python
from typing import Protocol

ORDER_STORAGE_PATH = "orders.txt"


class StorageUnavailable(Exception):
    pass


class Storage(Protocol):
    def save(self, data: str) -> None: ...
```

## Bad

```python
class FileStorage:
    def __init__(self, file_store, path):
        self.file_store = file_store
        self.path = path

    def save(self, data: str) -> None:
        try:
            self.file_store.replace_atomically(self.path, data)
        except FileStoreError as error:
            raise StorageUnavailable from error


class EncryptedFileStorage(FileStorage):
    def save(self, data: str) -> None:
        super().save(encrypt(data))
```

When requirements change again, you subclass again. The inheritance tree grows, and the base class becomes fragile.

## Good

```python
class FileStorage:
    def __init__(self, file_store, path):
        self.file_store = file_store
        self.path = path

    def save(self, data: str) -> None:
        try:
            self.file_store.replace_atomically(self.path, data)
        except FileStoreError as error:
            raise StorageUnavailable from error


class EncryptedStorage:
    def __init__(self, inner_storage: Storage):
        self.inner_storage = inner_storage

    def save(self, data: str) -> None:
        self.inner_storage.save(encrypt(data))


EncryptedStorage(FileStorage(file_store, ORDER_STORAGE_PATH)).save(data)
```

New requirements are handled by wrapping, with no change to existing units and no subclass. The power is in stacking:

```python
EncryptedStorage(CompressedStorage(FileStorage(file_store, ORDER_STORAGE_PATH))).save(data)
```

With inheritance, this means another subclass and another level of coupling. With composition, it is plain nesting. The `Storage` Protocol makes the shared contract explicit without coupling either implementation to the other.
