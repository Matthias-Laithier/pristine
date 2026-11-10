# CR-14 Value Dispatch Through a Registry

When one expression is compared against 3 or more constant values, each with its own work, that is dispatch, and an if/elif chain for it is forbidden. Write it as a registry: one dict literal in its owning module that maps each value to its handler and lists every case. When the language has no first-class functions, use its native dispatch structure, such as an exhaustive match where the compiler proves coverage. Two branches are no dispatch, and a plain `if/else` stays.

A value chain hides a table inside control flow. The reader must evaluate every condition to learn what exists, adding a case means editing a function that already works, and nothing lists the supported values. A registry states the same fact as data. The literal is the manifest of cases, and a new case is a new handler plus one entry, with no edit to the dispatcher.

The registry is a constant written once, in one place. Registration decorators, registration calls from other modules, and discovery by importing every module of a package are forbidden. They scatter the table across files, so a reader or an agent that searches for a name or follows imports never sees the full list of cases, and the registry depends on import order. A literal shows every case and every handler in one read. It is the registry form that [CR-7](cr-7-global-variables-are-config-never-mutated.md) and [CR-23](cr-23-code-is-greppable.md) require, and it is distinct from the extension point of [CO-7](co-7-make-extension-points-pluggable.md). This rule owns how multi-case value dispatch is written. CO-7 owns when a family of implementations becomes an extension point.

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


class UnsupportedPaymentEvent(Exception):
    pass


def on_succeeded(event):
    mark_invoice_paid(event.invoice_id)


def on_failed(event):
    schedule_retry(event.invoice_id)


def on_refunded(event):
    reopen_invoice(event.invoice_id)


HANDLERS = {
    "payment.succeeded": on_succeeded,
    "payment.failed": on_failed,
    "payment.refunded": on_refunded,
}


def handle_payment_event(event):
    handler = HANDLERS.get(event.type)
    if handler is None:
        raise UnsupportedPaymentEvent(event.type)
    handler(event)
```

The dispatcher never changes again: a fourth event type is one function plus one entry. The literal is the manifest of supported types, readable in one place, and the unknown case still fails loudly at the boundary.
