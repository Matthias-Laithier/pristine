# BS-11 Authorize Every Operation Against the Resource It Touches

Every entrypoint that reads or changes a resource checks that the authenticated principal may perform that action on that specific resource, before any effect. Scope the lookup by the owner or tenant of the principal in the same query that loads the resource. Deny by default: an operation without an explicit policy is refused, and a request without a known principal is refused. Identifiers in a request are claims. They prove no access.

Authentication says who calls. Authorization says whether this caller may act on this record. An endpoint that authenticates and then loads a record by the identifier in the request lets every user read every record by changing one number. Scoping the query itself leaves no separate check to forget, and a resource of another tenant answers as absent, so its existence does not leak.

An agent acting for a user holds that user's authority and nothing more. A tool call runs under the permissions of the user the agent serves and never under the service credentials of the application. A resource identifier in model output is a claim like any other request field.

The exceptions:
- Resources declared public by an explicit, named policy. The decision stays explicit.
- Background jobs acting for the system. They run under an explicit system principal with its own policy and never skip the check.

[CR-10](cr-10-business-logic-lives-in-the-backend.md) owns where authorization runs. This rule owns what it checks. [TST-2](tst-2-pin-the-boundaries.md) pins both sides of each permission boundary: the permitted caller and the refused one.

## Bad

```python
def get_invoice(invoice_repository, principal, invoice_identifier):
    invoice = invoice_repository.get(invoice_identifier, timeout=3)
    if invoice is None:
        raise InvoiceNotFound(invoice_identifier)
    return invoice
```

The principal is never consulted. Any signed-in user reads the invoices of every account by iterating identifiers.

## Good

```python
def get_invoice(invoice_repository, principal, invoice_identifier):
    invoice = invoice_repository.get_for_account(
        principal.account_identifier,
        invoice_identifier,
        timeout=3,
    )
    if invoice is None:
        raise InvoiceNotFound(invoice_identifier)
    return invoice
```

The lookup carries the account of the caller. An invoice of another account is indistinguishable from a missing one.
