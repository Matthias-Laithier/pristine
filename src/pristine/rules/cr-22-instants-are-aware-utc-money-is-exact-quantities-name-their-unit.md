# CR-22 Instants Are Aware UTC, Money Is Exact, Quantities Name Their Unit

Store, compare, and transmit instants as timezone-aware UTC values, or as ISO 8601 text with an offset. Convert to local time only for display, with the IANA zone of the user. Never create a naive datetime for an instant. Represent money as integer minor units with their currency, or as a decimal with explicit rounding, and never as a float. Account for every minor unit when splitting or rounding. A numeric value whose unit its type does not carry names the unit, such as `timeout_in_seconds`, `amount_in_cents`, and `size_in_bytes`, or uses a type that carries it, such as `timedelta`.

A naive datetime means different instants on different servers and shifts by an hour twice a year. A float cannot hold 0.10 exactly, so sums drift and splits lose cents. A setting named `retry_delay` reads as seconds to one author and milliseconds to the next.

The exceptions:
- Calendar values that are no instants, such as a birthday or an opening hour. Use a date or a local time and store its zone beside it.
- Measurements that tolerate float error, such as model scores or statistics.
- Names that an external library or protocol defines, such as the `timeout` parameter of an HTTP client. They keep their spelling at the call or inside their adapter (see [CR-4](cr-4-naming.md)).

[CR-18](cr-18-name-domain-significant-values.md) owns naming policy values. This rule owns the unit and representation of quantities. [CO-9](co-9-keep-side-effects-at-the-edges.md) owns the injected clock, and [BS-7](bs-7-represent-domain-invariants-in-types.md) owns value objects such as a money type.

## Bad: float money

```python
def split_bill(total, participant_count):
    share = round(total / participant_count, 2)
    return [share] * participant_count
```

A bill of 100.00 split three ways returns 33.33 three times. One cent disappears, and the float total cannot represent most amounts exactly.

## Good: exact money

```python
def split_bill_in_cents(total_in_cents, participant_count):
    share_in_cents, remainder_in_cents = divmod(total_in_cents, participant_count)
    larger_shares = [share_in_cents + 1] * remainder_in_cents
    smaller_shares = [share_in_cents] * (participant_count - remainder_in_cents)
    return larger_shares + smaller_shares
```

The amounts are exact integers, and the shares always sum to the bill.

## Bad: naive instant

```python
from datetime import datetime


def current_instant():
    return datetime.now()
```

The value carries the local zone of whichever server runs it, with no offset. Two servers record the same moment as two different times.

## Good: aware instant

```python
from datetime import UTC, datetime


def current_instant():
    return datetime.now(UTC)
```

Every instant carries its UTC offset and compares correctly across servers and daylight saving changes.
