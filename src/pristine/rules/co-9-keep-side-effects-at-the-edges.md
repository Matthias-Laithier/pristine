# CO-9 Keep Side Effects at the Edges

Domain logic receives explicit values and returns values. Network calls, database access, filesystem operations, environment access, clocks, randomness, and process state belong at the edges of the system. Put each effect behind an explicit boundary collaborator and supply that collaborator to the orchestration code that needs it. A unit never performs hidden I/O through an imported client or ambient runtime state.

Boundary collaborators can be services. A service is the preferred owner when an effect uses an external client or a resource lifecycle (see [CO-6](co-6-wrap-external-clients-in-singleton-services.md) and [CR-8](cr-8-services-live-in-a-dedicated-services-folder.md)). Orchestration code may sequence service calls and pass their results into pure domain logic. Its dependencies and effects stay visible in its interface.

This rule allows state changes inside the object that explicitly owns that state. It separates domain decisions from effects outside that ownership boundary. Inject clocks, randomness, and external services. Never read them implicitly (see [TST-6](tst-6-tests-are-deterministic.md)).

## Bad

```python
from typing import Protocol

BASIS_POINTS_PER_UNIT = 10_000


class TaxRateService(Protocol):
    def rate_in_basis_points(self, country: str) -> int: ...


def calculate_total(tax_rate_service: TaxRateService, invoice):
    tax_rate_in_basis_points = tax_rate_service.rate_in_basis_points(invoice.country)
    return invoice.subtotal_in_cents + invoice.subtotal_in_cents * tax_rate_in_basis_points // BASIS_POINTS_PER_UNIT
```

The domain calculation performs an external service call. Its dependency is visible, and pricing logic and boundary orchestration stay fused.

## Good

```python
from typing import Protocol

BASIS_POINTS_PER_UNIT = 10_000


class TaxRateService(Protocol):
    def rate_in_basis_points(self, country: str) -> int: ...


def calculate_total(subtotal_in_cents, tax_rate_in_basis_points):
    return subtotal_in_cents + subtotal_in_cents * tax_rate_in_basis_points // BASIS_POINTS_PER_UNIT


def price_invoice(tax_rate_service: TaxRateService, invoice):
    tax_rate_in_basis_points = tax_rate_service.rate_in_basis_points(invoice.country)
    return calculate_total(
        invoice.subtotal_in_cents,
        tax_rate_in_basis_points,
    )
```

The service performs the boundary operation, orchestration makes that dependency visible, and the domain calculation stays a pure transformation.

See [CO-4](co-4-clear-interfaces.md) for explicit collaborator contracts and [CO-13](co-13-imports-do-not-perform-external-work.md) for keeping edge setup out of module loading.
