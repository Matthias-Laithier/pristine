# CR-4 Naming

Names must be crystal clear. A longer name understood at once beats a shorter one that requires guessing. A name describes what the thing is or does. It never describes how it does it or where it lives. Established domain abbreviations such as `HTTP`, `URL`, and `API` are allowed. Ambiguous local shorthand is forbidden. `getUserByEmail` is clear. `handleData` is unclear.

Naming stays semantically consistent within each bounded context. If a concept is named `InvoiceRecipient`, every layer that shares that domain model uses the same term. Each layer may apply its conventional casing or serialization. A different bounded context may use a different term when the concepts differ.

[CR-18](cr-18-name-domain-significant-values.md) applies this rule to literals that encode policy, protocol semantics, units, thresholds, or statuses.

External APIs, legacy schemas, and protocols may impose names the application does not control. Translate those names once at an explicit boundary and use the application's canonical term everywhere behind it. Never spread external vocabulary through the domain model.

## Bad

```python
DISCOUNT_MINIMUM = 100


def calc(bp, tr):
    total = bp + bp * tr
    if total > DISCOUNT_MINIMUM:
        total = apply_disc(total)
    return total
```

The abbreviated names hide the domain and force the reader to reconstruct it from the operations.

## Good

```python
DISCOUNT_MINIMUM = 100


def calculate_total_price(base_price, tax_rate):
    total = base_price + base_price * tax_rate
    if total > DISCOUNT_MINIMUM:
        total = apply_discount(total)
    return total
```

Only the names changed. The calculation is identical, and its purpose and inputs are explicit.

## Bad: inconsistent names across services

```python
def send_invoice(recipient_email): ...
def send_payment_reminder(customer_contact): ...
def send_overdue_notice(addressee): ...
```

The same recipient concept has three names, so every caller must learn three vocabularies.

## Good: one name per concept

```python
def send_invoice(recipient_email): ...
def send_payment_reminder(recipient_email): ...
def send_overdue_notice(recipient_email): ...
```

Three names for one concept are three chances to misunderstand. One name is one lookup.
