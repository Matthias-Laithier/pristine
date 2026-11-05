# BS-10 Untrusted Values Never Change the Structure of a Query, Command, Markup, or Path

Every value that is not a literal in the source reaches an interpreter through the mechanism that keeps it data. Use bound parameters for SQL, an argument list without a shell for processes, an auto-escaping template or DOM API for markup, a path resolved and confirmed inside its base directory for files, and a URL whose host comes from an allowlist for outbound requests. Never build a query, a command, markup, a path, or a URL by formatting, concatenating, or interpolating such a value. Never pass such a value to `eval`, `exec`, or a deserializer that constructs arbitrary objects, such as `pickle.loads` or `yaml.load` without a safe loader.

Validation never makes a value safe for an interpreter. Each interpreter has its own grammar, and only its own parameter mechanism keeps a value out of it. A valid surname with an apostrophe breaks a SQL string, and a valid file name such as `../../settings.toml` escapes its directory. The rule judges how the structure is built, whatever the source of the value. Stored data and model output receive the same treatment as request input.

The exceptions:
- Identifiers that a parameter cannot carry, such as a sort column or a sort direction. Map the input to one of several literal fragments through a fixed mapping, and reject unknown keys.
- Query builders and ORMs that parameterize every value they receive.
- Markup produced by a sanitizing library at one owning boundary, then marked safe there.

[BS-1](bs-1-validate-untrusted-input-at-the-boundary.md) owns whether a value is acceptable. This rule owns how an accepted value reaches an interpreter. [BS-11](bs-11-authorize-every-operation-against-the-resource-it-touches.md) owns whether the caller may touch the resource a path or a query names.

## Bad

```python
def find_invoices_by_recipient(database, recipient_email):
    return database.fetch_all(
        f"SELECT number, amount_in_cents FROM invoices WHERE recipient_email = '{recipient_email}'",
        timeout=3,
    )
```

The input `x' OR '1'='1` returns the invoices of every customer, and a valid address containing an apostrophe breaks the query.

## Good

```python
def find_invoices_by_recipient(database, recipient_email):
    return database.fetch_all(
        "SELECT number, amount_in_cents FROM invoices WHERE recipient_email = :recipient_email",
        {"recipient_email": recipient_email},
        timeout=3,
    )
```

The address travels as a bound parameter. No value can change what the query selects.
