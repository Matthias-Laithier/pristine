# CO-12 Localize Mutation

Keep mutation inside one explicit owner. Prefer immutable domain values and functions that return a new value. When mutation is required, the object, module, or transaction that owns the state exposes the operations that may change it. Never pass a mutable collection or object among unrelated units and let each one modify it directly.

Localized mutation makes state transitions visible and keeps invariants at one boundary. It also prevents callers from changing state without the owner's validation. [CR-7](cr-7-global-variables-are-config-never-mutated.md) owns global state. This rule applies to state at every scope.

The exceptions:
- In-place work inside a function, when the mutable value is created there, does not escape while partially built, and is returned in a valid state.
- Performance-sensitive mutation, when measurement justifies it and one owner still controls it.
- Caches and registries, which may mutate behind their owning interface during their declared lifecycle.

## Bad

```python
from enum import StrEnum


class OrderStatus(StrEnum):
    UNPAID = "unpaid"
    PAID = "paid"


def apply_discount(order_data, discount_in_cents):
    order_data["total_in_cents"] -= discount_in_cents


def mark_paid(order_data, paid_at):
    order_data["status"] = OrderStatus.PAID
    order_data["paid_at"] = paid_at
```

Any caller holding the dictionary can create a negative total, a paid order without a payment time, or another undocumented state.

## Good

```python
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum


class OrderStatus(StrEnum):
    UNPAID = "unpaid"
    PAID = "paid"


@dataclass(frozen=True)
class Order:
    total_in_cents: int
    status: OrderStatus = OrderStatus.UNPAID
    paid_at: datetime | None = None

    def __post_init__(self):
        if self.total_in_cents < 0:
            raise ValueError("total_in_cents must not be negative")
        if (self.status is OrderStatus.PAID) != (self.paid_at is not None):
            raise ValueError("paid status and paid_at must agree")


def apply_discount(order, discount_in_cents):
    return replace(
        order,
        total_in_cents=order.total_in_cents - discount_in_cents,
    )


def mark_paid(order, paid_at):
    return replace(
        order,
        status=OrderStatus.PAID,
        paid_at=paid_at,
    )
```

The same total and payment state change only through operations that return a valid immutable order. No caller can alter an existing order behind the back of another consumer.
