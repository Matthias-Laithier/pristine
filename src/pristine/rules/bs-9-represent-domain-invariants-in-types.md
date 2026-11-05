# BS-9 Represent Domain Invariants in Types

After validation, represent domain state so that invalid combinations cannot be constructed or are rejected at construction. Use value objects, enums, distinct variants, constrained collections, or constructors that enforce related fields together. Never carry a lifecycle or multi-field invariant through the application as unrelated primitives and booleans that can later form impossible combinations.

Create a domain type when fields must agree, when a value has behavior across several operations, or when independent construction would repeatedly risk violating its rules. Do not wrap every string or integer. A primitive is enough when it is validated at the boundary, stays immutable afterward, and has no related state that can contradict it. Promote it to a value object when those conditions stop holding.

Validation at the boundary stays the responsibility of [BS-1](bs-1-validate-untrusted-input-at-the-boundary.md). This rule owns the trusted representation that validation produces. External schemas may permit states the domain rejects. Translate them at the boundary and fail explicitly when they cannot produce a valid domain value.

## Bad

```python
from dataclasses import dataclass, replace
from datetime import datetime


@dataclass(frozen=True)
class Subscription:
    account_identifier: str
    is_active: bool
    is_cancelled: bool
    cancelled_at: datetime | None
    cancellation_reason: str | None


def cancel_subscription(subscription, cancelled_at, cancellation_reason):
    return replace(
        subscription,
        is_active=False,
        is_cancelled=True,
        cancelled_at=cancelled_at,
        cancellation_reason=cancellation_reason,
    )
```

The type permits a subscription to be active and cancelled, or cancelled without a time or a reason. Every consumer must rediscover the valid combinations.

## Good

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ActiveSubscription:
    account_identifier: str


@dataclass(frozen=True)
class CancelledSubscription:
    account_identifier: str
    cancelled_at: datetime
    cancellation_reason: str

    def __post_init__(self):
        if not self.cancellation_reason.strip():
            raise ValueError("cancellation_reason must not be empty")


def cancel_subscription(subscription, cancelled_at, cancellation_reason):
    return CancelledSubscription(
        account_identifier=subscription.account_identifier,
        cancelled_at=cancelled_at,
        cancellation_reason=cancellation_reason,
    )
```

The data and the transition are unchanged, and each lifecycle state has exactly the fields it requires. Consumers cannot receive an active subscription carrying cancellation data or a cancelled subscription missing it.
