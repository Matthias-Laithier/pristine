# CR-11 Every Change Includes Cleanup

Every code change includes a cleanup pass over the behavior and dependencies it touches. Delete code, tests, exports, feature flags, compatibility paths, dependencies, configuration, documentation, and assets that the change makes obsolete. A change stays unfinished while the implementation or structure it replaces remains in the codebase.

[CR-20](cr-20-minimize-the-resulting-codebase.md) owns whether machinery needs to exist. This rule owns removing obsolete parts and repairing the touched structure.

Used code can still be debt. Simplify touched control flow, collapse unnecessary layers and wrappers, repair misplaced responsibilities and unclear boundaries, split or merge units whose structure stopped fitting, and rename concepts the change exposes as unclear. Leave the touched area in the simplest coherent shape that supports the present behavior.

Tests are code and receive the same cleanup. Delete tests for removed behavior and redundant protection. Simplify fixtures and helpers made obsolete by the new structure. Keep every test that still protects supported behavior (see [TST-3](tst-3-minimal-test-count.md)).

Never postpone visible cleanup in touched code to a later refactor. The relevant context is cheapest while making the change. This rule authorizes no unrelated rewrite and no deletion of code whose usage is unknown. Persisted data, public contracts, active migrations, and external consumers are concrete requirements. Investigate uncertainty before deleting.

## Bad

`backend/src/pricing.py`:

```python
USE_LEGACY_PRICING = False


class PricingCalculator:
    def calculate(self, order):
        if USE_LEGACY_PRICING:
            return LegacyPricingCalculator().calculate(order)
        return CurrentPricingCalculator().calculate(order)


class CurrentPricingCalculator:
    def calculate(self, order):
        return sum(line.unit_price_in_cents * line.quantity for line in order.lines)


class LegacyPricingCalculator:
    def calculate(self, order):
        total_in_cents = 0
        for line in order.lines:
            total_in_cents += line.unit_price_in_cents * line.quantity
        return total_in_cents
```

`backend/tests/test_pricing.py`:

```python
from pricing import LegacyPricingCalculator, PricingCalculator


def test_pricing_calculator_sums_line_totals(order):
    assert PricingCalculator().calculate(order) == 4200


def test_legacy_pricing_calculator_sums_line_totals(order):
    assert LegacyPricingCalculator().calculate(order) == 4200
```

The new path shipped, and the disabled flag, the replaced implementation, the obsolete test, and the unnecessary class layers remain. Every future change must understand structure the product does not need.

## Good

`backend/src/pricing.py`:

```python
def calculate_order_total_in_cents(order):
    return sum(line.unit_price_in_cents * line.quantity for line in order.lines)
```

`backend/tests/test_pricing.py`:

```python
from pricing import calculate_order_total_in_cents


def test_calculate_order_total_in_cents_sums_line_totals(order):
    assert calculate_order_total_in_cents(order) == 4200
```

Only the supported behavior, the simplest structure that expresses it, and the test that protects it remain. The change reduces both code and structural debt.

See [CR-5](cr-5-dry-don-t-repeat-yourself.md) for eliminating duplicate behavior, [CR-15](cr-15-group-files-by-cohesive-responsibility.md) for repairing directory structure, [CO-2](co-2-small-focused-units.md) for repairing responsibilities, and [CO-5](co-5-functions-where-possible-classes-where-needed.md) for removing unnecessary class structure.
