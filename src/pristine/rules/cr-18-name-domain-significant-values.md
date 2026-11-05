# CR-18 Name Domain-Significant Values

Replace a magic literal with a named domain concept. A literal is magic when its meaning or ownership is unclear at the use site, or when the same policy value must stay consistent across uses. Use the representation that fits the concept: a constant, an enum, a value object, a configuration field, or a domain type. The name explains why the value exists and does more than repeat its spelling. Model identifiers and sampling settings such as temperature are configuration fields, and a call site never holds them as literals, even as named arguments.

Do not extract every literal. These may stay inline: obvious local values such as zero, one, an empty collection, or an array index, self-describing protocol values inside their owning adapter, named arguments that make a local value unambiguous, and one-off presentation text. Concrete test inputs and expected outputs also stay inline when the test name and assertions make their role clear. A constant such as `FIVE = 5` adds indirection without meaning. Repetition is a discovery signal and never the criterion. One unexplained policy value deserves a name, while ten unrelated zeroes may not.

Values controlled by configuration or an external protocol belong at their boundary. A generic constants module is the wrong home for them. Keep each named value beside the policy or adapter that owns it. A model identifier or a sampling setting changes on its own schedule and is judged by evals (see [TST-8](tst-8-model-quality-is-measured-by-evals-code-by-deterministic-tests.md)), so it lives in configuration. A literal `"gpt-4o"` or `temperature=0.2` at a call site lets a model switch miss one caller. [CR-9](cr-9-assets-live-in-an-organized-assets-folder.md) owns prompt templates and eval datasets. [CR-4](cr-4-naming.md) owns the clarity of the name.

## Bad

```python
def delivery_price_in_cents(order_total_in_cents, customer_tier):
    if order_total_in_cents >= 5000 or customer_tier == "gold":
        return 0
    return 700
```

The numbers and the string encode delivery and customer policy, and nothing names those meanings or units.

## Good

```python
from enum import StrEnum

FREE_DELIVERY_MINIMUM_IN_CENTS = 5_000
STANDARD_DELIVERY_PRICE_IN_CENTS = 700


class CustomerTier(StrEnum):
    GOLD = "gold"


def delivery_price_in_cents(order_total_in_cents, customer_tier):
    if order_total_in_cents >= FREE_DELIVERY_MINIMUM_IN_CENTS or customer_tier is CustomerTier.GOLD:
        return 0
    return STANDARD_DELIVERY_PRICE_IN_CENTS
```

The policy reads in domain terms. Zero stays inline because a zero cost is immediate, while the threshold, the price, and the tier receive names that explain their roles.
