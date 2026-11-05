# CR-19 Keep One Level of Abstraction per Function

A function reads at one level of abstraction. An orchestration function sequences named domain or boundary operations. A focused implementation function performs the lower-level parsing, serialization, mapping, or calculation its interface names. Never interrupt a high-level workflow with protocol fields, byte manipulation, SQL fragments, or serialization details.

Extract a lower-level block only when it has a meaningful responsibility and name. A trivial expression may stay inline when extraction would create a helper that explains nothing. The goal is a readable flow. One statement per function is no goal.

This rule owns vertical consistency inside a function. [CO-2](co-2-small-focused-units.md) owns the number of responsibilities, and [CR-12](cr-12-function-size.md) owns length. A short function can still mix levels.

## Bad

```python
import json
from collections.abc import Mapping


def import_invoice(invoice_repository, raw_payload):
    payload = json.loads(raw_payload)
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    recipient = payload.get("recipient")
    amount_in_cents = payload.get("amount_in_cents")
    if not isinstance(recipient, str) or not recipient.strip():
        raise ValueError("recipient must be a non-empty string")
    if type(amount_in_cents) is not int or amount_in_cents <= 0:
        raise ValueError("amount_in_cents must be a positive integer")
    invoice = Invoice(recipient, amount_in_cents)
    invoice_repository.save(invoice, timeout=3)
```

The function begins as workflow orchestration, drops into JSON shape validation, then returns to domain construction and persistence.

## Good

```python
import json
from collections.abc import Mapping


def parse_invoice(raw_payload):
    payload = json.loads(raw_payload)
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    recipient = payload.get("recipient")
    amount_in_cents = payload.get("amount_in_cents")
    if not isinstance(recipient, str) or not recipient.strip():
        raise ValueError("recipient must be a non-empty string")
    if type(amount_in_cents) is not int or amount_in_cents <= 0:
        raise ValueError("amount_in_cents must be a positive integer")
    return Invoice(recipient, amount_in_cents)


def import_invoice(invoice_repository, raw_payload):
    invoice = parse_invoice(raw_payload)
    invoice_repository.save(invoice, timeout=3)
```

The orchestration reads as parse then save. The parser owns one lower-level job and converts untrusted JSON into a trusted domain value.
