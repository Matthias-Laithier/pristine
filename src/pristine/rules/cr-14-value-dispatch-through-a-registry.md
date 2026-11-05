# CR-14 Value Dispatch Through a Registry

When one expression is compared against 3 or more constant values, each with its own work, that is dispatch, and an if/elif chain for it is forbidden. Write it as a registry: a dict owned by its module, populated through a registration decorator, with one entry per case. When the language has no first-class functions or module-level registration, use its native dispatch structure: a dispatch dict where that is idiomatic, an exhaustive match where the compiler proves coverage. Two branches are no dispatch, and a plain `if/else` stays.

A value chain hides a table inside control flow. The reader must evaluate every condition to learn what exists, adding a case means editing a function that already works, and nothing lists the supported values. A registry states the same fact as data. Listing the registry gives the manifest of cases, and a new case is a new definition plus one registration, with no edit to the dispatcher.

The registry here is deliberately light: one dict, one module, one registration decorator. It is the encapsulated registry mechanism that [CR-7](cr-7-global-variables-are-config-never-mutated.md) permits, and it is distinct from the extension point of [CO-7](co-7-make-extension-points-pluggable.md). Registration rejects duplicate keys, consumers cannot write to the registry directly, and decorators perform no external work, as [CO-13](co-13-imports-do-not-perform-external-work.md) requires. This rule owns how multi-case value dispatch is written. CO-7 owns when a family of implementations becomes a full extension point populated across modules.

A value from outside the boundary can be unknown (see [BS-1](bs-1-validate-untrusted-input-at-the-boundary.md)). The dispatch site rejects the unknown case explicitly with a raise. A lookup that returns `None` and moves on swallows the failure (see [BS-4](bs-4-do-not-swallow-failures.md)).

Guard sequences are no dispatch. Guards reject distinct invalid conditions one after another, no single value is forked against constants, and they stay guards (see [CR-13](cr-13-nesting-depth.md)). This rule triggers only when the same expression is compared against 3 or more constants.

Generated files keep the dispatch their generator writes (see [CR-3](cr-3-no-comments-except-machine-read-text.md)).

## Bad

```python
class UnsupportedPaymentEvent(Exception):
    pass


def handle_payment_event(event):
    if event.type == "payment.succeeded":
        mark_invoice_paid(event.invoice_id)
    elif event.type == "payment.failed":
        schedule_retry(event.invoice_id)
    elif event.type == "payment.refunded":
        reopen_invoice(event.invoice_id)
    else:
        raise UnsupportedPaymentEvent(event.type)
```

One function forks on `event.type` against three constants. A fourth event type means editing this function again, the set of supported types exists nowhere as data, and the reader must evaluate three conditions to reach the case they came for.

## Good

```python
__all__ = ["UnsupportedPaymentEvent", "handle_payment_event"]

_HANDLERS = {}


class UnsupportedPaymentEvent(Exception):
    pass


def handles(event_type):
    def register(handler):
        if event_type in _HANDLERS:
            raise ValueError(f"duplicate event type: {event_type}")
        _HANDLERS[event_type] = handler
        return handler

    return register


@handles("payment.succeeded")
def on_succeeded(event):
    mark_invoice_paid(event.invoice_id)


@handles("payment.failed")
def on_failed(event):
    schedule_retry(event.invoice_id)


@handles("payment.refunded")
def on_refunded(event):
    reopen_invoice(event.invoice_id)


def handle_payment_event(event):
    handler = _HANDLERS.get(event.type)
    if handler is None:
        raise UnsupportedPaymentEvent(event.type)
    handler(event)
```

The dispatcher never changes again: a fourth event type is one function plus one decorator. Each case owns a self-contained unit, the registry doubles as the manifest of supported types, and the unknown case still fails loudly at the boundary.
