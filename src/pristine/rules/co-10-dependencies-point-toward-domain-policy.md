# CO-10 Dependencies Point Toward Domain Policy

Dependencies point from volatile delivery and infrastructure details toward stable domain policy. Domain code never imports web frameworks, database clients, ORM models, cloud SDKs, command-line adapters, or concrete service implementations. Define the contract beside the policy that needs it, implement that contract at the edge, and connect the two in the composition root.

An acyclic dependency graph can still point in the wrong direction. If changing a database or a framework forces changes to business rules, infrastructure owns the policy. [CO-8](co-8-no-circular-dependencies.md) forbids cycles. This rule owns the direction of the edges that remain.

Framework-owned entrypoints and framework extension types are exceptions. Keep them at the edge and translate their values into domain values before calling policy. Small applications may place layers in one package, and their imports still point toward the domain.

## Bad

`pricing.py`:

```python
from infrastructure.sql_orders import SqlOrderRepository


def total_order_lines(order):
    return sum(line.unit_price_in_cents * line.quantity for line in order.lines)


def calculate_order_total(database_session, order_identifier):
    order_repository = SqlOrderRepository(database_session)
    order = order_repository.get(order_identifier, timeout=3)
    return total_order_lines(order)
```

Pricing imports and constructs a concrete SQL repository. Replacing the database changes domain code.

## Good

`pricing.py`:

```python
from typing import Protocol


class OrderRepository(Protocol):
    def get(self, order_identifier, timeout): ...


def total_order_lines(order):
    return sum(line.unit_price_in_cents * line.quantity for line in order.lines)


def calculate_order_total(order_repository: OrderRepository, order_identifier):
    order = order_repository.get(order_identifier, timeout=3)
    return total_order_lines(order)
```

`main.py`:

```python
order_repository = SqlOrderRepository(database_session)
total_in_cents = calculate_order_total(order_repository, order_identifier)
```

Pricing owns the repository contract it needs. Infrastructure implements that contract, and the composition root connects them.
