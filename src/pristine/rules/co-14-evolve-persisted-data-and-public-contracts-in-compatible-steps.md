# CO-14 Evolve Persisted Data and Public Contracts in Compatible Steps

A change to a stored schema, a message format, a public API, or a published event keeps every deployed reader and writer working. Change a persisted schema only through a versioned migration of the project's migration tool. Never edit a migration that has run outside a developer machine. Ship a breaking change in three releases: expand with the new shape beside the old one, migrate writers, readers, and existing data, then contract by removing the old shape once nothing uses it. Adding an optional field is compatible. Removing, renaming, or changing the type or meaning of a field is breaking.

Deployments are never atomic. During a rollout, old and new code run against the same database and queue, and a rollback runs old code against new data. An edited migration leaves every environment that already ran it in a schema no file describes.

The exceptions:
- A schema or contract with no deployed data and no external consumer. Change it freely and squash its migrations.
- A new major version of a public API, served beside the old version for a declared deprecation period.

[CO-11](co-11-export-only-the-public-contract.md) owns the surface of a contract. This rule owns how it changes. [CR-11](cr-11-every-change-includes-cleanup.md) owns removing the old shape in the contract step.

## Bad

`migrations/0007_rename_customer_email.py`:

```python
def upgrade(schema):
    schema.rename_column("customers", "email", "contact_email")
```

Instances of the previous release still query `email` during the rollout and fail, and a rollback runs against a column that no longer exists.

## Good

`migrations/0007_add_customer_contact_email.py`:

```python
def upgrade(schema):
    schema.add_column("customers", "contact_email", "text", nullable=True)
```

Both releases run against this schema. Writers fill both columns, a batched backfill copies existing rows, and a later migration drops `email` once no release reads it.
