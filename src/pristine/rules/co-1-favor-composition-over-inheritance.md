# CO-1 Favor Composition Over Inheritance

Favor composition. Use inheritance only when the subtype can replace the parent everywhere without violating the parent's contract and polymorphic substitution is the purpose of the relationship. The "is a" and "has a" test is a useful first signal and no proof. If you subclass only to reuse code or change behavior, compose. Deep inheritance trees are a smell.

The exception is a framework that explicitly defines inheritance as its extension mechanism.

Add a behavior variant by wrapping or combining units, such as a storage that encrypts and then delegates to another storage. Never modify or subclass a stable unit only to create the variant. Bug fixes and intended changes to the contract belong in the unit that owns the behavior.

## Bad

```python
class InvoiceExporter(PostgresInvoiceRepository):
    def export(self, invoice_identifier):
        invoice = self.get(invoice_identifier)
        return render_invoice(invoice)
```

An exporter is no repository. Inheritance exposes the repository API and ties exporting to one storage implementation only to reuse `get`.

## Good

```python
class InvoiceExporter:
    def __init__(self, invoice_repository):
        self.invoice_repository = invoice_repository

    def export(self, invoice_identifier):
        invoice = self.invoice_repository.get(invoice_identifier)
        return render_invoice(invoice)
```

The exporter has a repository. Any repository implementation can be supplied without changing the exporter or pretending it is a repository.
