# CO-8 No Circular Dependencies

The dependency graph is acyclic. No file, module, package, component, or layer depends directly or indirectly on itself. This applies to production code, tests, tooling, and configuration. A cycle is forbidden even when the language or runtime can resolve it.

Lazy imports, dynamic imports, `TYPE_CHECKING` guards, and service locators fix no circular dependency. They hide an edge or delay its execution and keep the architectural cycle.

Break a cycle in one of three ways:
- Move a genuinely shared contract or value into a lower-level unit that depends on neither side.
- Invert one dependency through a stable contract assembled at the composition root.
- Merge units that cannot be separated.

Never create a vague `common` module only to relocate the cycle.

## Bad

`orders.py`:

```python
from dataclasses import dataclass

from discounts import discount_for


@dataclass(frozen=True)
class Order:
    subtotal_in_cents: int
    is_preferred_customer: bool


def total_in_cents(order):
    return order.subtotal_in_cents - discount_for(order)
```

`discounts.py`:

```python
from orders import Order

MAX_PREFERRED_CUSTOMER_DISCOUNT_IN_CENTS = 1_000


def discount_for(order: Order):
    if order.is_preferred_customer:
        return min(
            MAX_PREFERRED_CUSTOMER_DISCOUNT_IN_CENTS,
            order.subtotal_in_cents,
        )
    return 0
```

`orders` depends on `discounts`, which depends on `orders`. A clean import fails against a partially initialized module, and neither module can be reused independently.

## Good

`order.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    subtotal_in_cents: int
    is_preferred_customer: bool
```

`discounts.py`:

```python
from order import Order

MAX_PREFERRED_CUSTOMER_DISCOUNT_IN_CENTS = 1_000


def discount_for(order: Order):
    if order.is_preferred_customer:
        return min(
            MAX_PREFERRED_CUSTOMER_DISCOUNT_IN_CENTS,
            order.subtotal_in_cents,
        )
    return 0
```

`pricing.py`:

```python
from discounts import discount_for
from order import Order


def total_in_cents(order: Order):
    return order.subtotal_in_cents - discount_for(order)
```

Pricing and discounts depend in one direction on the shared `Order` value, and no dependency path returns to its origin.

See [CO-4](co-4-clear-interfaces.md) for defining stable contracts, [CO-7](co-7-make-extension-points-pluggable.md) for keeping concrete implementations outside core logic, and [CO-10](co-10-dependencies-point-toward-domain-policy.md) for the direction of the remaining dependency edges.
