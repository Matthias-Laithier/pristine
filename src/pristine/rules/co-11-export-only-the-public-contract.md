# CO-11 Export Only the Public Contract

Expose the smallest public API that lets consumers use a module or package correctly. Keep parsing helpers, storage details, caches, framework adapters, and intermediate representations private. Consumers depend on public entrypoints and domain values, and never on internal names that happen to be importable.

Every public name is a compatibility promise. An accidental export blocks cleanup because external consumers may rely on it. Declare exports with the native mechanism of the ecosystem when one exists. Test the public behavior and leave the internal surface untested.

A reusable lower-level utility may be public when consumers genuinely need its independent contract. Promote it deliberately, name that contract, and test it directly. Never expose internals only to make tests convenient. [CO-4](co-4-clear-interfaces.md) owns the clarity of a contract. This rule owns its surface area.

## Bad

`invoices/__init__.py`:

```python
from .delivery import normalize_recipient, render_invoice_payload, send_invoice
from .invoice import Invoice
```

```python
from invoices import normalize_recipient, render_invoice_payload


def send_monthly_invoice(invoice, mailer):
    recipient = normalize_recipient(invoice.recipient)
    payload = render_invoice_payload(invoice)
    mailer.send(recipient, payload, timeout=3)
```

The package exposes its helpers with no declared contract, and the consumer assembles internal invoice steps. Renaming a helper or changing the payload format breaks code outside the package.

## Good

`invoices/__init__.py`:

```python
from .delivery import send_invoice
from .invoice import Invoice

__all__ = ["Invoice", "send_invoice"]
```

```python
from invoices import send_invoice


def send_monthly_invoice(invoice, mailer):
    send_invoice(invoice, mailer)
```

The package promises two public concepts. Parsing and rendering can change without affecting consumers.
